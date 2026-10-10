# Security policy and trust boundaries

Do not submit credentials, personal data or nonpublic incident evidence to this sandbox. Report suspected vulnerabilities privately to the repository owner rather than including exploit secrets in a public issue.

Controls in this release: server-derived tenant identities, role checks, separate-actor approvals, expiring plan digests, request bounds, per-key rate limits, HMAC events, idempotent effect transactions, allowlisted MCP tools, and no arbitrary model code or shell execution. Credentials stay out of child-tool environments and generated source artifacts.

Limitations: static bearer keys are not SSO; SQLite tenant filtering is application-enforced, not database RLS; the DB is not encrypted by the application; audit events are not tamper-evident; exact source quotations are not a guarantee against prompt injection or hallucinated interpretation; the Python fixture subprocess is not a general security sandbox; per-key limits do not protect against unauthenticated distributed denial of service.

Only trusted administrators may configure the model gateway URL. Never expose the service without TLS and network controls. Never configure arbitrary MCP servers from model output. See docs/PRODUCTION.md before handling real user workloads.
