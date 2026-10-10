import asyncio
import pytest
from fastapi.testclient import TestClient
from apps.api.main import create_app
from agentforge.config import Settings

OP = "operator-test-key-000000000000"
APPROVER = "approver-test-key-000000000000"
OTHER = "other-tenant-key-000000000000"
ADMIN = "admin-test-key-00000000000000"
VIEW = "viewer-test-key-0000000000000"


def headers(key=OP, idem="request-1"):
    return {"Authorization": "Bearer " + key, "Idempotency-Key": idem}


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "test.db"),
        worker_enabled=False,
        webhook_secret="test-webhook-secret",
        llm_key="",
        keys={
            OP: {"tenant": "one", "subject": "operator", "role": "operator"},
            APPROVER: {"tenant": "one", "subject": "reviewer", "role": "approver"},
            OTHER: {"tenant": "two", "subject": "other", "role": "admin"},
            ADMIN: {"tenant": "one", "subject": "operator", "role": "admin"},
            VIEW: {"tenant": "one", "subject": "viewer", "role": "viewer"},
        },
    )
    with TestClient(create_app(settings)) as client:
        yield client


def process(client):
    run = client.app.state.store.claim()
    assert run
    asyncio.run(client.app.state.runtime.process(run))
    return client.app.state.store.get(run["tenant"], run["id"])
