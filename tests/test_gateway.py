import asyncio
import json
import httpx
import pytest
from agentforge.config import Settings
from agentforge.gateway import Gateway
from agentforge.store import Store
from agentforge.models import RunRequest


def fixture(tmp_path):
    store = Store(tmp_path / "gateway.db")
    settings = Settings(llm_key="test-provider-key", fallback_model="fallback")
    run = store.create_run(
        "one",
        "live",
        RunRequest(
            scenario="incident", prompt="Investigate latency", mode="live", budget_tokens=16000
        ).model_dump(),
        "operator",
    )
    return Gateway(settings, store), run


def mock_client(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)
    )


def test_live_structured_response_fallback_and_tenant_cache(tmp_path, monkeypatch):
    gateway, run = fixture(tmp_path)
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload["model"])
        if len(calls) == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Rollback with approval",
                                    "action": "rollback",
                                    "citations": [],
                                    "risk": "medium",
                                }
                            )
                        }
                    }
                ],
                "usage": {"total_tokens": 120},
            },
        )

    mock_client(monkeypatch, handler)

    async def scenario():
        result = await gateway.generate("one", run["id"], run["state"], "planner", {})
        assert result["action"] == "rollback"
        assert len(calls) == 2
        await gateway.generate("one", run["id"], run["state"], "planner", {})
        assert len(calls) == 2
        other = gateway.store.create_run("two", "live", run["request"], "operator")
        await gateway.generate("two", other["id"], other["state"], "planner", {})
        assert len(calls) == 3

    asyncio.run(scenario())


def test_budget_stops_before_provider(tmp_path, monkeypatch):
    gateway, run = fixture(tmp_path)
    run["state"]["usage"] = 16000

    def forbidden(request):
        raise AssertionError("Must not contact provider after budget exhaustion")

    mock_client(monkeypatch, forbidden)
    with pytest.raises(RuntimeError, match="budget"):
        asyncio.run(gateway.generate("one", run["id"], run["state"], "planner", {}))


def test_live_never_falls_back_to_demo(tmp_path):
    gateway, run = fixture(tmp_path)
    gateway.settings.llm_key = ""
    with pytest.raises(RuntimeError, match="no demo fallback"):
        asyncio.run(gateway.generate("one", run["id"], run["state"], "planner", {}))


def test_invalid_structured_output_rejected(tmp_path, monkeypatch):
    gateway, run = fixture(tmp_path)
    mock_client(
        monkeypatch,
        lambda req: httpx.Response(200, json={"choices": [{"message": {"content": '{"action":"shell"}'}}]}),
    )
    with pytest.raises(ValueError):
        asyncio.run(gateway.generate("one", run["id"], run["state"], "planner", {}))
