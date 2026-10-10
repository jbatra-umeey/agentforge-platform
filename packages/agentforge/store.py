"""Tenant scoped durable state. SQLite transactions serialize claims and side effects.
Single-host deployment only; shared-network filesystems are unsupported.
"""

import hashlib
import json
from pathlib import Path
import sqlite3
import time
import uuid
from contextlib import contextmanager


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Store:
    def __init__(self, path):
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO schema_version VALUES(1);
            CREATE TABLE IF NOT EXISTS runs(
              id TEXT PRIMARY KEY, tenant TEXT NOT NULL, idem TEXT NOT NULL,
              request TEXT NOT NULL, status TEXT NOT NULL, state TEXT NOT NULL,
              created REAL NOT NULL, updated REAL NOT NULL, lease REAL NOT NULL DEFAULT 0,
              UNIQUE(tenant,idem));
            CREATE TABLE IF NOT EXISTS audit(
              seq INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL, run_id TEXT NOT NULL,
              kind TEXT NOT NULL, payload TEXT NOT NULL, at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS docs(
              id TEXT PRIMARY KEY, tenant TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL);
            CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(id UNINDEXED,tenant UNINDEXED,title,text);
            CREATE TABLE IF NOT EXISTS effects(
              tenant TEXT NOT NULL, run_id TEXT NOT NULL, result TEXT NOT NULL,
              PRIMARY KEY(tenant,run_id));
            CREATE TABLE IF NOT EXISTS cache(
              key TEXT PRIMARY KEY, value TEXT NOT NULL, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS rate_limits(
              identity TEXT PRIMARY KEY, window INTEGER NOT NULL, count INTEGER NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def audit(self, tenant, run_id, kind, payload, db=None):
        if db is None:
            with self.connect() as conn:
                return self.audit(tenant, run_id, kind, payload, conn)
        db.execute(
            "INSERT INTO audit(tenant,run_id,kind,payload,at) VALUES(?,?,?,?,?)",
            (tenant, run_id, kind, canonical(payload), time.time()),
        )

    def create_run(self, tenant, idem, request, subject):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM runs WHERE tenant=? AND idem=?", (tenant, idem)).fetchone()
            if row:
                if row["request"] != canonical(request):
                    raise ValueError("Idempotency key already used for a different request")
                return self.decode(row)
            now = time.time()
            run_id = str(uuid.uuid4())
            state = {"request": request, "creator": subject, "stages": {}, "usage": 0}
            db.execute(
                "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)",
                (run_id, tenant, idem, canonical(request), "queued", canonical(state), now, now, 0),
            )
            self.audit(tenant, run_id, "queued", {"actor": subject}, db)
            return self.get(tenant, run_id, db)

    def decode(self, row):
        if not row:
            return None
        value = dict(row)
        value["state"] = json.loads(value["state"])
        value["request"] = json.loads(value["request"])
        value.pop("idem", None)
        return value

    def get(self, tenant, run_id, db=None):
        if db is None:
            with self.connect() as conn:
                return self.get(tenant, run_id, conn)
        return self.decode(
            db.execute("SELECT * FROM runs WHERE tenant=? AND id=?", (tenant, run_id)).fetchone()
        )

    def list(self, tenant):
        with self.connect() as db:
            return [
                self.decode(r)
                for r in db.execute(
                    "SELECT * FROM runs WHERE tenant=? ORDER BY created DESC LIMIT 100", (tenant,)
                )
            ]

    def events(self, tenant, run_id):
        with self.connect() as db:
            return [
                dict(r) | {"payload": json.loads(r["payload"])}
                for r in db.execute(
                    "SELECT seq,kind,payload,at FROM audit WHERE tenant=? AND run_id=? ORDER BY seq",
                    (tenant, run_id),
                )
            ]

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM runs WHERE status='queued' OR (status='running' AND lease<?) ORDER BY created LIMIT 1",
                (time.time(),),
            ).fetchone()
            if not row:
                return None
            db.execute(
                "UPDATE runs SET status='running',lease=?,updated=? WHERE id=?",
                (time.time() + 180, time.time(), row["id"]),
            )
            return self.get(row["tenant"], row["id"], db)

    def heartbeat(self, tenant, run_id):
        with self.connect() as db:
            db.execute(
                "UPDATE runs SET lease=? WHERE tenant=? AND id=? AND status='running'",
                (time.time() + 180, tenant, run_id),
            )

    def save(self, tenant, run_id, state, status="running"):
        with self.connect() as db:
            db.execute(
                "UPDATE runs SET state=?,status=?,updated=? WHERE tenant=? AND id=?",
                (canonical(state), status, time.time(), tenant, run_id),
            )

    def approve(self, tenant, run_id, supplied_digest, approved, actor):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            run = self.get(tenant, run_id, db)
            if not run:
                raise LookupError("Run not found")
            state = run["state"]
            if run["status"] != "awaiting_approval" or state.get("approval_digest") != supplied_digest:
                raise ValueError("Approval is stale or already consumed")
            if time.time() > state["approval_expires"]:
                raise ValueError("Approval expired; create a new run")
            if state["creator"] == actor:
                raise PermissionError("A different operator must approve this run")
            state["approval"] = {"approved": approved, "actor": actor, "digest": supplied_digest}
            status = "queued" if approved else "rejected"
            db.execute(
                "UPDATE runs SET state=?,status=?,updated=? WHERE id=?",
                (canonical(state), status, time.time(), run_id),
            )
            self.audit(tenant, run_id, "approved" if approved else "rejected", {"actor": actor}, db)
            return self.get(tenant, run_id, db)

    def put_doc(self, tenant, title, text):
        doc_id = digest([tenant, title, text])[:24]
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            exists = db.execute("SELECT 1 FROM docs WHERE id=?", (doc_id,)).fetchone()
            if not exists:
                db.execute("INSERT INTO docs VALUES(?,?,?,?)", (doc_id, tenant, title, text))
                db.execute("INSERT INTO docs_fts VALUES(?,?,?,?)", (doc_id, tenant, title, text))
        return doc_id

    def search(self, tenant, query):
        import re

        tokens = re.findall(r"[A-Za-z0-9]{2,}", query)[:40]
        if not tokens:
            return []
        fts = " OR ".join('"' + x + '"' for x in tokens)
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id AS source_id,title,text,bm25(docs_fts) AS score FROM docs_fts WHERE docs_fts MATCH ? AND tenant=? ORDER BY score LIMIT 5",
                    (fts, tenant),
                )
            ]

    def cache_get(self, key):
        with self.connect() as db:
            row = db.execute(
                "SELECT value FROM cache WHERE key=? AND expires>?", (key, time.time())
            ).fetchone()
            return json.loads(row["value"]) if row else None

    def cache_put(self, key, value):
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO cache VALUES(?,?,?)", (key, canonical(value), time.time() + 3600)
            )

    def rate_limit(self, identity, limit=120):
        window = int(time.time() // 60)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO rate_limits VALUES(?,?,1) ON CONFLICT(identity) DO UPDATE SET count=CASE WHEN window=excluded.window THEN count+1 ELSE 1 END,window=excluded.window",
                (identity, window),
            )
            return (
                db.execute("SELECT count FROM rate_limits WHERE identity=?", (identity,)).fetchone()["count"]
                <= limit
            )
