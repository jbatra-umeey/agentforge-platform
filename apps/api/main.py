import asyncio
from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import time
import uuid
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from agentforge.config import Settings
from agentforge.models import RunRequest, Approval, Document, Event, CAPABILITIES
from agentforge.runtime import Runtime
from agentforge.store import Store
from agentforge.telemetry import registry


def create_app(settings=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        settings.validate()
        app.state.store = Store(settings.db_path)
        app.state.runtime = Runtime(settings, app.state.store)
        task = asyncio.create_task(app.state.runtime.worker()) if settings.worker_enabled else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    app = FastAPI(title="AgentForge", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )

    @app.middleware("http")
    async def bounds(request, call_next):
        try:
            content_length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return Response(status_code=400)
        if content_length > 100000:
            return Response(status_code=413)
        # Enforce the actual body bound even when Content-Length is absent or dishonest.
        if request.method in ("POST", "PUT", "PATCH"):
            received = bytearray()
            async for chunk in request.stream():
                received.extend(chunk)
                if len(received) > 100000:
                    return Response(status_code=413)
            request._body = bytes(received)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    def identity(authorization: str = Header(default="")):
        token = authorization.removeprefix("Bearer ")
        actor = None
        for key, value in settings.keys.items():
            if hmac.compare_digest(key, token) and authorization.startswith("Bearer "):
                actor = value
        if not actor:
            raise HTTPException(401, "Valid bearer credential required")
        if not app.state.store.rate_limit(hashlib.sha256(token.encode()).hexdigest()):
            raise HTTPException(429, "Rate limit exceeded")
        return actor

    def role(actor, allowed):
        if actor["role"] not in allowed:
            raise HTTPException(403, "Role does not permit this operation")

    def find(actor, run_id):
        run = app.state.store.get(actor["tenant"], run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        return run

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.2.0"}

    @app.get("/ready")
    def ready():
        with app.state.store.connect() as db:
            db.execute("SELECT 1").fetchone()
        return {"status": "ready", "storage": "sqlite-single-host", "production_certified": False}

    @app.get("/me")
    def me(actor=Depends(identity)):
        return actor

    @app.get("/capabilities")
    def capabilities(actor=Depends(identity)):
        return {
            "capabilities": CAPABILITIES,
            "live_model_configured": bool(settings.llm_key),
            "release_status": "executable sandbox reference; production qualification pending",
        }

    @app.get("/runs")
    def list_runs(actor=Depends(identity)):
        return app.state.store.list(actor["tenant"])

    @app.post("/runs", status_code=202)
    def create_run(body: RunRequest, actor=Depends(identity), idempotency_key: str = Header(default="")):
        role(actor, ("operator", "admin"))
        if body.mode == "live" and not settings.llm_key:
            raise HTTPException(503, "Live mode requires a configured model key")
        if not 1 <= len(idempotency_key) <= 120:
            raise HTTPException(422, "Idempotency-Key header required (1–120 characters)")
        try:
            return app.state.store.create_run(
                actor["tenant"], idempotency_key, body.model_dump(), actor["subject"]
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.get("/runs/{run_id}")
    def get_run(run_id: str, actor=Depends(identity)):
        return find(actor, run_id)

    @app.get("/runs/{run_id}/events")
    def events(run_id: str, actor=Depends(identity)):
        find(actor, run_id)
        return app.state.store.events(actor["tenant"], run_id)

    @app.post("/runs/{run_id}/approval")
    def approve(run_id: str, body: Approval, actor=Depends(identity)):
        role(actor, ("approver", "admin"))
        try:
            return app.state.store.approve(
                actor["tenant"], run_id, body.digest, body.approve, actor["subject"]
            )
        except LookupError:
            raise HTTPException(404, "Run not found") from None
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.post("/documents", status_code=201)
    def document(body: Document, actor=Depends(identity)):
        role(actor, ("operator", "admin"))
        return {"source_id": app.state.store.put_doc(actor["tenant"], body.title, body.text)}

    @app.get("/documents/search")
    def search(q: str, actor=Depends(identity)):
        if len(q) > 4000:
            raise HTTPException(422, "Query too long")
        return app.state.store.search(actor["tenant"], q)

    @app.post("/events", status_code=202)
    async def ingest(
        request: Request,
        actor=Depends(identity),
        x_signature: str = Header(default=""),
        x_timestamp: str = Header(default=""),
    ):
        role(actor, ("operator", "admin"))
        if not settings.webhook_secret:
            raise HTTPException(503, "Webhook signing is not configured")
        raw = await request.body()
        try:
            timestamp = int(x_timestamp)
        except ValueError:
            raise HTTPException(401, "Invalid event timestamp") from None
        signature = hmac.new(
            settings.webhook_secret.encode(), x_timestamp.encode() + b"." + raw, hashlib.sha256
        ).hexdigest()
        if abs(time.time() - timestamp) > 300 or not hmac.compare_digest(signature, x_signature):
            raise HTTPException(401, "Invalid or expired event signature")
        try:
            event = Event.model_validate_json(raw)
        except ValueError:
            raise HTTPException(422, "Invalid event envelope") from None
        if event.request.mode == "live" and not settings.llm_key:
            raise HTTPException(503, "Live mode requires a configured model key")
        try:
            return app.state.store.create_run(
                actor["tenant"], "event:" + event.event_id, event.request.model_dump(), actor["subject"]
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.get("/metrics")
    def metrics(actor=Depends(identity)):
        role(actor, ("admin",))
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    @app.get("/runs/{run_id}/artifact")
    def artifact(run_id: str, actor=Depends(identity)):
        run = find(actor, run_id)
        if run["status"] != "completed":
            raise HTTPException(409, "Artifact is available after successful evaluation")
        return Response(
            json.dumps(run["state"]["stages"]["execute"], indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="agentforge-{uuid.UUID(run_id)}.json"'},
        )

    return app


app = create_app()
