"""Exercise all five workflows against an already-running API, including approval."""

import json
import os
import uuid
from agentforge_sdk import AgentForge

keys = json.loads(os.environ["AGENTFORGE_KEYS"])
operator = next(k for k, v in keys.items() if v["role"] == "operator")
approver = next(k for k, v in keys.items() if v["role"] == "approver")
base = os.getenv("API_URL", "http://localhost:8000")
with AgentForge(base, operator) as api, AgentForge(base, approver) as reviewer:
    api.document(
        "Checkout latency runbook",
        "Checkout latency above 300ms after release v2 requires rollback to v1. Verify p95 after rollback.",
    )
    report = []
    for scenario in ("incident", "sdlc", "knowledge", "workflow", "reliability"):
        if scenario == "workflow":
            run = api.event(
                str(uuid.uuid4()), scenario, "Evaluate support renewal vendors", os.environ["WEBHOOK_SECRET"]
            )
        else:
            run = api.run(scenario, "Investigate checkout latency and release rollback with evidence")
        run = api.wait(run["id"])
        if run["status"] == "awaiting_approval":
            reviewer.approve(run)
            run = api.wait(run["id"])
        assert run["status"] == "completed", run
        assert run["state"]["stages"]["evaluate"]["passed"]
        report.append(
            {
                "scenario": scenario,
                "run_id": run["id"],
                "status": run["status"],
                "evaluation": run["state"]["stages"]["evaluate"],
            }
        )
    print(json.dumps(report, indent=2))
