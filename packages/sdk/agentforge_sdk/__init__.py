import hashlib
import hmac
import json
import time
import uuid
import httpx


class AgentForge:
    def __init__(self, base_url, token, transport=None):
        self.client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
            transport=transport,
            trust_env=False,
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()

    def request(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    def run(self, scenario, prompt, mode="demo", idempotency_key=None):
        return self.request(
            "POST",
            "/runs",
            json={"scenario": scenario, "prompt": prompt, "mode": mode},
            headers={"Idempotency-Key": idempotency_key or str(uuid.uuid4())},
        )

    def get(self, run_id):
        return self.request("GET", f"/runs/{run_id}")

    def wait(self, run_id, timeout=120):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            run = self.get(run_id)
            if run["status"] not in ("queued", "running"):
                return run
            time.sleep(0.5)
        raise TimeoutError("Run did not settle within the deadline")

    def approve(self, run, approve=True):
        return self.request(
            "POST",
            f"/runs/{run['id']}/approval",
            json={"digest": run["state"]["approval_digest"], "approve": approve},
        )

    def document(self, title, text):
        return self.request("POST", "/documents", json={"title": title, "text": text})

    def event(self, event_id, scenario, prompt, secret):
        raw = json.dumps({"event_id": event_id, "request": {"scenario": scenario, "prompt": prompt}}).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
        return self.request(
            "POST",
            "/events",
            content=raw,
            headers={"Content-Type": "application/json", "X-Timestamp": timestamp, "X-Signature": signature},
        )
