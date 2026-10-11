# Operating the sandbox profile

## Credentials

Run `python3 scripts/init_env.py` once. The owner-readable `.env` contains independent operator, approver and admin identities for tenant `demo`. Do not commit it. Add tenants by adding server-side credential mappings with different tenant identifiers. Rotate by replacing a key and restarting the API; never reuse a creator subject for an approver. The UI stores credentials only in component memory; refresh or switch identity clears them.

## Single-host deployment

Use the checked-in Compose file. Images run unprivileged, drop Linux capabilities, deny privilege escalation, use read-only root filesystems and bound temporary storage. The API data volume remains writable. Ports bind to `127.0.0.1` and require a separately configured HTTPS reverse proxy before any remote access. Resource limits are conservative defaults for the sandbox, not load-tested sizing.

Next.js API proxy routing is baked at build time via `API_INTERNAL_URL`. Rebuild the web image if the internal API hostname changes. `.env` is never copied into images. Production startup requires an HTTPS model endpoint and at least a 32-character webhook secret, but these checks alone do not make a deployment production ready.

`/health` reports process liveness; `/ready` checks the database. Metrics require an admin bearer key. API errors avoid returning provider response bodies. Do not treat audit payloads as tamper-proof records.

## Recovery

For a worker crash, restart the API and allow up to 180 seconds for a previous lease to expire. Completed stages are reused. Awaiting approvals persist; their one-hour expiry still applies. Failed runs remain failed with their error classification. Create a new request with a fresh idempotency key to retry a failed workflow after correcting its cause.

Backup with `python scripts/backup.py data/agentforge.db backups/agentforge-YYYYMMDD.db`. The SQLite backup API creates a consistent snapshot, checks integrity and restricts output permissions. To restore, stop the API, preserve the old data volume, restore the backup as the database file with the API user's ownership, then start the API and validate tenant records. Do not restore over a running SQLite database or leave unrelated WAL/SHM files from a different snapshot. Run a rehearsal against a disposable environment first.

## Events

POST `/events` with the operator bearer key, JSON envelope `{event_id, request}`, timestamp header `X-Timestamp` and hex `X-Signature = HMAC-SHA256(secret, timestamp + '.' + raw_body)`. Timestamps expire after five minutes. Repeated tenant/event IDs return the same run; changed content returns conflict. `AgentForge.event()` signs requests for you.

## Live-provider verification

Configure a dedicated test model account. Test valid structured output, rate-limit fallback, malformed output, provider timeouts, token reservations, and usage reconciliation. The automated gateway suite uses HTTP mocks and cannot certify the real provider. Avoid storing secrets in documents or goals. The response cache stores model output in the database for one hour; tenant isolation does not replace a retention policy.

## Failure triage

- 401: missing/invalid credential or invalid event signature.
- 403: insufficient role or self-approval attempt.
- 404: unknown run or a different tenant's run.
- 409: conflicting idempotency key, expired/stale approval, or unavailable artifact.
- 429: credential rate limit; retry after the minute window.
- 503: live model or event signing not configured.
- Failed grounding: add relevant evidence and create a new run.
- Pending approval: use a distinct approver identity and review the reflected plan.

Never solve a failing safety gate by disabling it. Fix the configuration or create a narrower proposal.
