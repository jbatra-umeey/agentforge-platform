import asyncio
import time
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from .gateway import Gateway, ACTIONS
from .tools import ToolClient
from .store import digest
from .telemetry import tracer, latency, runs


class GraphState(TypedDict):
    tenant: str
    run_id: str
    state: dict


class Runtime:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store
        self.gateway, self.tools = Gateway(settings, store), ToolClient(store)
        graph = StateGraph(GraphState)
        names = ("observe", "plan", "critic", "reflect", "policy", "execute", "evaluate")
        for name in names:
            graph.add_node(name, self.node(name))
        graph.add_edge(START, "observe")
        for a, b in zip(names, names[1:]):
            if a == "policy":
                graph.add_conditional_edges(
                    a, lambda s: "stop" if s["state"].get("waiting") else "go", {"stop": END, "go": b}
                )
            else:
                graph.add_edge(a, b)
        graph.add_edge("evaluate", END)
        self.graph = graph.compile()

    def node(self, name):
        async def call(g):
            tenant, run_id, state = g["tenant"], g["run_id"], g["state"]
            stages = state["stages"]
            if name in stages and name != "policy":
                return g
            with tracer.start_as_current_span("agentforge." + name) as span, latency.labels(name).time():
                span.set_attribute("run.id", run_id)
                scenario = state["request"]["scenario"]
                if name == "observe":
                    observation = await self.tools.call(
                        tenant, run_id, "inspect_scenario", {"scenario": scenario}
                    )
                    documents = self.store.search(tenant, state["request"]["prompt"])
                    output = {"observation": observation, "documents": documents}
                elif name == "plan":
                    output = await self.gateway.generate(tenant, run_id, state, "planner", stages["observe"])
                elif name == "critic":
                    output = await self.gateway.generate(
                        tenant, run_id, state, "critic", {"proposal": stages["plan"], **stages["observe"]}
                    )
                elif name == "reflect":
                    output = await self.gateway.generate(
                        tenant,
                        run_id,
                        state,
                        "reflector",
                        {"proposal": stages["plan"], "review": stages["critic"], **stages["observe"]},
                    )
                elif name == "policy":
                    proposal = stages["reflect"]
                    if proposal["action"] != ACTIONS[scenario]:
                        raise PermissionError("Model action is outside scenario allowlist")
                    if not stages["critic"]["approved"]:
                        raise PermissionError("Critic rejected the proposal")
                    docs = {d["source_id"]: d["text"] for d in stages["observe"]["documents"]}
                    valid = all(
                        c["source_id"] in docs and c["quote"] in docs[c["source_id"]]
                        for c in proposal["citations"]
                    )
                    if not valid or (scenario == "knowledge" and not proposal["citations"]):
                        raise PermissionError("Grounding gate failed: missing or invalid source quotes")
                    state["approval_digest"] = digest(
                        {
                            "run_id": run_id,
                            "proposal": proposal,
                            "observation": stages["observe"],
                            "mode": state["request"]["mode"],
                        }
                    )
                    needs_approval = scenario in ("incident", "sdlc", "workflow")
                    approved = state.get("approval", {}).get("approved", False)
                    state["waiting"] = needs_approval and not approved
                    state.setdefault("approval_expires", time.time() + 3600)
                    if approved and state["approval"]["digest"] != state["approval_digest"]:
                        raise PermissionError("Approved plan no longer matches execution")
                    output = {
                        "allowed": True,
                        "human_approval_required": needs_approval,
                        "citation_quotes_valid": valid,
                    }
                elif name == "execute":
                    output = await self.tools.call(
                        tenant, run_id, "apply_approved_action", {"action": stages["reflect"]["action"]}
                    )
                else:
                    result = stages["execute"]
                    passed = {
                        "incident": result.get("verified"),
                        "sdlc": result.get("tests_passed") == 4,
                        "knowledge": bool(result.get("citations")),
                        "workflow": result.get("amount_usd", 1001) <= 1000,
                        "reliability": result.get("gate_passed"),
                    }[scenario]
                    output = {
                        "passed": bool(passed),
                        "scope": "sandbox workflow contract",
                        "grounding": "exact quote validation; semantic entailment is not measured",
                    }
                    if not passed:
                        raise RuntimeError("Execution evaluation failed")
                stages[name] = output
                self.store.save(tenant, run_id, state)
                self.store.audit(tenant, run_id, name, {"completed": True})
            return g

        return call

    async def heartbeat(self, run):
        while True:
            await asyncio.sleep(30)
            self.store.heartbeat(run["tenant"], run["id"])

    async def process(self, run):
        tenant, run_id = run["tenant"], run["id"]
        state = run["state"]
        beat = asyncio.create_task(self.heartbeat(run))
        try:
            await self.graph.ainvoke({"tenant": tenant, "run_id": run_id, "state": state})
            status = "awaiting_approval" if state.get("waiting") else "completed"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Keep provider response bodies/keys out of client-visible failures.
            status = "failed"
            state["error"] = (
                str(exc) if isinstance(exc, (PermissionError, RuntimeError)) else type(exc).__name__
            )
        finally:
            beat.cancel()
            await asyncio.gather(beat, return_exceptions=True)
        self.store.save(tenant, run_id, state, status)
        self.store.audit(tenant, run_id, status, {"status": status})
        runs.labels(state["request"]["scenario"], status).inc()

    async def worker(self):
        while True:
            run = self.store.claim()
            if run:
                await self.process(run)
            else:
                await asyncio.sleep(0.25)
