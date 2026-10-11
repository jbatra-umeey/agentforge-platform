# Validation record — 2026-10-10

This record reports observed results rather than production readiness.

- Backend suite: **35 tests passed** in the initial full run (30.53 seconds). Includes real MCP subprocess calls for all five workflows, isolation, approval replay/expiry/self-approval, idempotent concurrent effects, lease claims, fresh-runtime resume and backup restore.
- Ruff: passed for application, SDK, scripts and tests.
- Python compilation: passed.
- Next.js optimized build: passed with Next 16.4.0 and React 19.3.0.
- `npm audit --omit=dev --audit-level=high`: **0 known vulnerabilities** in the resolved production dependency graph.
- `pip-audit` against the hash-pinned Python lock: **no known vulnerabilities found**.
- HTTP integration: **all five workflows completed** against the running API, including the signed webhook and independent approval identities.
- Live model integration: gateway contract tests use mocked provider responses; no real model result is claimed.
- Local browser execution: **blocked before assertions** because the Chromium download returned an invalid archive. This is not a UI test pass.
- Local Docker deployment: unavailable because this editing environment has no Docker executable.
- GitHub Actions: the committed workflow performs container builds, five HTTP demos, browser assertions and restart persistence checks. Consult the exact commit's Actions run; workflow presence alone is not evidence of success.

The HTTP demo runner, container checks and browser suite are reproducible in CI. Changes after this initial record must be assessed against their own checks. Production deployment remains unverified until the additional gates in PRODUCTION.md are satisfied.
