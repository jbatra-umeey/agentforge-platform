import hashlib
import hmac
import json
import time
import pytest
from conftest import headers, OP, APPROVER, OTHER, ADMIN, VIEW, process
from agentforge.models import RunRequest


def start(client, scenario="incident", idem="request-1"):
    response = client.post(
        "/runs",
        headers=headers(idem=idem),
        json={"scenario": scenario, "prompt": "Investigate checkout latency and release rollback"},
    )
    assert response.status_code == 202, response.text
    return response.json()


@pytest.mark.parametrize("scenario", ["incident", "sdlc", "knowledge", "workflow", "reliability"])
def test_five_real_mcp_workflows(client, scenario):
    client.post(
        "/documents",
        headers=headers(),
        json={"title": "Runbook", "text": "Checkout latency above 300ms requires rollback after release v2."},
    )
    run = start(client, scenario)
    run = process(client)
    if scenario in ("incident", "sdlc", "workflow"):
        assert run["status"] == "awaiting_approval", run["state"]
        assert "execute" not in run["state"]["stages"]
        response = client.post(
            f"/runs/{run['id']}/approval",
            headers=headers(APPROVER),
            json={"digest": run["state"]["approval_digest"], "approve": True},
        )
        assert response.status_code == 200
        run = process(client)
    assert run["status"] == "completed", run["state"]
    assert run["state"]["stages"]["evaluate"]["passed"]
    assert len(run["state"]["stages"]) == 7
    assert client.get(f"/runs/{run['id']}/artifact", headers=headers()).status_code == 200
    events = client.get(f"/runs/{run['id']}/events", headers=headers()).json()
    assert any(e["kind"] == "tool_effect" for e in events)


@pytest.mark.parametrize("path", ["/runs", "/capabilities", "/metrics", "/documents/search?q=secret"])
def test_auth_required(client, path):
    assert client.get(path).status_code == 401


def test_health_and_readiness(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").json()["production_certified"] is False
    assert len(client.get("/capabilities", headers=headers()).json()["capabilities"]) == 12


def test_tenant_isolation_and_artifacts(client):
    run = start(client)
    for suffix in ("", "/events", "/artifact"):
        assert client.get(f"/runs/{run['id']}{suffix}", headers=headers(OTHER)).status_code == 404
    assert client.get("/runs", headers=headers(OTHER)).json() == []
    client.post(
        "/documents",
        headers=headers(),
        json={"title": "Secret", "text": "Unique private checkout secret content"},
    )
    assert client.get("/documents/search?q=checkout", headers=headers(OTHER)).json() == []
    assert len(client.get("/documents/search?q=checkout", headers=headers()).json()) == 1


def test_idempotency_and_conflict(client):
    first = start(client)
    second = start(client)
    assert first["id"] == second["id"]
    response = client.post("/runs", headers=headers(), json={"scenario": "sdlc", "prompt": "Another request"})
    assert response.status_code == 409


def test_roles(client):
    assert (
        client.post(
            "/runs", headers=headers(VIEW), json={"scenario": "incident", "prompt": "Investigate this"}
        ).status_code
        == 403
    )
    assert client.get("/metrics", headers=headers()).status_code == 403
    assert client.get("/metrics", headers=headers(ADMIN)).status_code == 200


def test_validation_live_and_body_bounds(client):
    assert (
        client.post("/runs", headers=headers(), json={"scenario": "bad", "prompt": "hello"}).status_code
        == 422
    )
    assert (
        client.post(
            "/runs", headers=headers(), json={"scenario": "incident", "prompt": "hello", "mode": "live"}
        ).status_code
        == 503
    )
    assert (
        client.post(
            "/runs", headers=headers(), json={"scenario": "incident", "prompt": "hello", "tenant": "other"}
        ).status_code
        == 422
    )
    assert client.post("/runs", headers=headers(), content=b"x" * 100001).status_code == 413


def test_approval_replay_wrong_digest_role_and_self(client):
    start(client)
    run = process(client)
    url = f"/runs/{run['id']}/approval"
    body = {"digest": run["state"]["approval_digest"], "approve": True}
    assert client.post(url, headers=headers(), json=body).status_code == 403
    assert client.post(url, headers=headers(ADMIN), json=body).status_code == 403
    assert client.post(url, headers=headers(OTHER), json=body).status_code == 404
    assert client.post(url, headers=headers(APPROVER), json=body | {"digest": "a" * 64}).status_code == 409
    assert client.post(url, headers=headers(APPROVER), json=body).status_code == 200
    assert client.post(url, headers=headers(APPROVER), json=body).status_code == 409


def test_rejection(client):
    start(client)
    run = process(client)
    r = client.post(
        f"/runs/{run['id']}/approval",
        headers=headers(APPROVER),
        json={"digest": run["state"]["approval_digest"], "approve": False},
    )
    assert r.json()["status"] == "rejected"
    assert client.app.state.store.claim() is None


def test_expired_approval(client):
    start(client)
    run = process(client)
    run["state"]["approval_expires"] = time.time() - 1
    client.app.state.store.save("one", run["id"], run["state"], "awaiting_approval")
    assert (
        client.post(
            f"/runs/{run['id']}/approval",
            headers=headers(APPROVER),
            json={"digest": run["state"]["approval_digest"], "approve": True},
        ).status_code
        == 409
    )


def test_knowledge_fails_without_grounding(client):
    start(client, "knowledge")
    run = process(client)
    assert run["status"] == "failed"
    assert "Grounding" in run["state"]["error"]


def test_signed_events_deduplicate_and_reject_tamper(client):
    raw = json.dumps(
        {"event_id": "evt-1", "request": {"scenario": "workflow", "prompt": "Review vendors"}}
    ).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(b"test-webhook-secret", timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    auth = headers() | {
        "X-Timestamp": timestamp,
        "X-Signature": signature,
        "Content-Type": "application/json",
    }
    first = client.post("/events", headers=auth, content=raw)
    assert first.status_code == 202
    assert client.post("/events", headers=auth, content=raw).json()["id"] == first.json()["id"]
    assert client.post("/events", headers=auth, content=raw + b" ").status_code == 401
    assert client.post("/events", headers=auth | {"X-Timestamp": "0"}, content=raw).status_code == 401


def test_rate_limit(client):
    store = client.app.state.store
    assert all(store.rate_limit("example", 3) for _ in range(3))
    assert not store.rate_limit("example", 3)


def test_empty_keys_fail_closed(tmp_path):
    from agentforge.config import Settings

    with pytest.raises(ValueError):
        Settings(db_path=str(tmp_path / "db"), keys={}).validate()


def test_production_requires_tls_and_webhook_secret():
    from agentforge.config import Settings

    with pytest.raises(ValueError):
        Settings(
            environment="production",
            base_url="http://bad",
            keys={OP: {"tenant": "x", "subject": "x", "role": "admin"}},
        ).validate()


def test_default_request_is_explicit_demo():
    assert RunRequest(scenario="incident", prompt="Investigate").mode == "demo"
