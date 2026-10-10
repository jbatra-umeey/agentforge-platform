# ◈ AgentForge

**An executable agent operations monorepo: evidence → planning → review → approval → tools → evaluation.**

[![Validate executable platform](https://github.com/jbatra-umeey/agentforge-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/jbatra-umeey/agentforge-platform/actions/workflows/ci.yml)

> **Release status: sandbox reference implementation, not production certified.**
> All five workflows execute API, LangGraph, MCP and persistent-state code. Demo mode uses an explicitly deterministic planner; live mode uses a configured OpenAI-compatible model. Tools operate on local sandbox fixtures. No incident rollback changes your cloud, no purchase sends money, and the SDLC demo does not open an external GitHub PR. See [validation evidence](docs/VALIDATION.md) and [production release gates](docs/PRODUCTION.md).

## Run it

Requires Docker Engine + Compose v2, Python 3.12 to generate credentials, and optional model credentials for live mode.

```bash
git clone https://github.com/jbatra-umeey/agentforge-platform.git
cd agentforge-platform
python3 scripts/init_env.py
docker compose up --build --wait
```

Open **http://localhost:3000**. Read your local `.env` and connect using the generated **operator** key. Keys are generated randomly, never supplied as shared defaults. Add the included runbook from **Evidence library**. Start a workflow. For an action requiring approval, switch identity to the separate **approver** key, select the pending run and review it before approving.

The API is at `http://localhost:8000`; OpenAPI is at `/docs`. Ports bind to loopback. Do not expose development credentials or this deployment directly to the internet.

### Without Docker

```bash
make setup       # dependencies + unique .env; refuses to overwrite an existing .env
make api         # terminal 1
make web         # terminal 2
make demo        # terminal 3: all five workflows, including signed event and approvals
```

`make demo` needs the API running. It deliberately uses both identities to automate the sandbox demonstration; that script is not a human approval process for production.

### Live models

Set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` in `.env`, restart the API, and select **Live** in the UI. `LLM_BASE_URL` can point to an OpenAI-compatible gateway such as LiteLLM; `FALLBACK_MODEL` configures a second model on that endpoint. The provider must support Chat Completions JSON-schema responses. Missing credentials, invalid output, exhausted token reservations and provider failures fail closed. **There is no fallback from live mode to canned demo output.** Sandbox execution remains sandbox execution in live mode.

## Five executable demos

| Workflow | Actual execution | Boundary |
|---|---|---|
| Incident commander | Inspect synthetic latency evidence → plan/review → approve → write rollback state → evaluate recovery fixture | Local synthetic service, not production telemetry |
| SDLC engineer | Inspect AF-101 → approve → execute failing subscription regression → apply trusted repair → run four passing assertions → download diff and source | Fixed checked-in Python fixture; no arbitrary generated-code execution or external PR |
| Knowledge investigator | Ingest tenant document → BM25 search → synthesis → exact source-quote validation → cited artifact | Lexical retrieval; quote validity does not establish semantic entailment |
| Workflow automation | Signed/replay-protected webhook → vendor policy → approval → idempotent purchase-order ledger | No real purchase or payment |
| Reliability lab | Replay arithmetic dataset → run baseline and repaired candidate → score both → evaluate gate | Program contract benchmark, not a measured LLM-quality benchmark |

## Twelve implemented capabilities

| Capability | Implementation |
|---|---|
| Structured output | Strict Pydantic request, proposal, citation and review contracts |
| Grounded retrieval | Tenant-scoped SQLite FTS5/BM25, stable source IDs, exact quote validation |
| Bounded agent planning | LangGraph observe → plan → critic → reflect → policy → execute → evaluate |
| MCP orchestration | Actual stdio client/server with two allowlisted tools and scoped child environment |
| Persistent memory | Durable run state, stage checkpoints, evidence and audit records |
| Human approval | RBAC, separate actor, expiring proposal digest, single-use transition |
| Model routing | Configured primary/fallback, tenant-specific response cache, conservative token reservations |
| Event execution | Timestamped HMAC envelope, durable queue, event idempotency |
| Debate | Separate planner and critic model calls with persisted review |
| Reflection | Separate reflector call informed by critic and evidence, followed by hard policy checks |
| Observability/evaluation | OpenTelemetry stage spans, Prometheus counters/histograms, audit trail, execution gates |
| Reusable SDK | Installable Python HTTP client for runs, documents, approvals and signed events |

In demo mode the planner, critic and reflector are deterministic fixtures. In live mode they are independent role calls to configured models, not a claim of independent model intelligence or guaranteed consensus. [Implementation details](docs/ARCHITECTURE.md).

## Validation

```bash
make test
# API must be running for the following:
make demo
set -a; . ./.env; set +a
npm run test:e2e --prefix apps/web
```

CI runs backend security/workflow tests, dependency audits, Docker Compose build/health checks, five HTTP demos, Playwright UI tests and a persisted-state restart check. Green CI validates this sandbox profile; it does not certify a cloud deployment or real provider integration.

## Repository layout

```text
apps/api/             FastAPI authentication and HTTP contracts
apps/web/             Next.js dashboard and Playwright tests
packages/agentforge/  LangGraph runtime, MCP, gateway, storage, telemetry
packages/sdk/         Installable Python client
scripts/              Credentials, five-demo runner, backup and persistence checks
infra/                Optional OpenTelemetry collector configuration
tests/                Isolation, approval, recovery, gateway and workflow tests
docs/                 Architecture, operations, validation and release gates
```

## Operations and security

Read [SECURITY.md](SECURITY.md), [deployment/runbook](docs/OPERATIONS.md), and [remaining production requirements](docs/PRODUCTION.md). SQLite/WAL supports the tested single-host profile. This release does not implement PostgreSQL RLS, pgvector, Redis, Temporal, OIDC/SSO, Kubernetes, arbitrary untrusted-code isolation or external cloud/GitHub side effects. Those are explicit remaining integration work, not silently simulated capabilities.

MIT licensed. Contributions should include a reproducible workflow or a meaningful security/recovery regression test.
