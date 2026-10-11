# Production qualification: outstanding

The current release is an executable single-host sandbox reference. It is not a completed commercial or cloud-operated agent platform. The following gates must pass before a production claim.

| Gate | Current state | Required evidence |
|---|---|---|
| Backend behavior and security regressions | Local tests passed; see VALIDATION | Repeat on exact release commit |
| Container deployment and browser E2E | CI configured; verify the actual Actions result | Healthy containers, all browser assertions and restart test |
| Real model providers | Typed integration implemented; provider tests mocked | Live credentials, contract/cost/latency tests and outage exercise |
| Real incident/SDLC/vendor systems | Sandbox adapters only | Scoped cloud/GitHub/vendor adapters, externally reconciled idempotency, separate approval scopes |
| Authentication | Scoped bearer keys and RBAC | OIDC/SSO, secret manager rotation, revocation, session controls |
| Multi-host persistence | SQLite/WAL single host | Migration design, PostgreSQL RLS tests, backup/restore and failover drills |
| RAG quality | BM25 plus literal quote validation | Representative corpus, retrieval recall, semantic grounding, injection/red-team evaluation |
| Generated code execution | Trusted fixture templates only | Isolated execution service, network isolation, filesystem quotas and exploit tests |
| Operational security | Local controls and dependency scans | SAST/DAST, external assessment, TLS, egress controls, retention and incident plan |
| Reliability/scale | Functional tests | Load/soak tests, SLOs, chaos tests, canary and rollback exercise |
| Telemetry | OTel/Prometheus integration | Collector ingestion verification, alert routing and sensitive-data review |
| Release operations | CI build/smoke workflow | Signed immutable images, SBOM/provenance, deployment approvals and target-environment checks |

Do not interpret green fixture tests, an architecture diagram, or a published GitHub repository as proof that these gates passed. Do not advertise synthetic incident recovery numbers as measured production improvements. The incident's metrics and the purchasing data are fixtures; the reliability lab compares programs rather than LLM models.

No cloud account, domain, deployment target, real model credential or external-system secret was required to run the offline demo profile. Deploying production infrastructure and completing provider-specific integration require those concrete inputs and validation in the target environment.
