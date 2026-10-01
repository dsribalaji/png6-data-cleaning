# Threat model (Level 3 D-1)

This page looks at the four paths where the planner meets untrusted input or sensitive data: **upload**, **LLM**, **export** and **sign-in**. It uses **STRIDE**, a checklist of six threat kinds:

- **S**poofing: pretending to be someone else.
- **T**ampering: changing data you shouldn't.
- **R**epudiation: denying you did something.
- **I**nformation disclosure: seeing data you shouldn't.
- **D**enial of service: making the system unusable.
- **E**levation of privilege: doing more than your role allows.

Each row names a control that exists in the code, with where to find it and which test proves it, or marks the threat as an **accepted risk** with the reason. Reviewed 2026-10-01 against `main`.

## Upload path (`POST /api/v1/datasets` → ingest → profile)

| STRIDE | Threat | Control (evidence) |
|---|---|---|
| S | An anonymous caller uploads a file | Only `data_engineer` and `administrator` can upload: `require_roles` in `modules/datasets/features/upload_dataset/router.py`; every route is checked by `tests/api/test_route_auth_coverage.py` |
| T | The original file is altered after upload (FR-004) | Raw files are written once under `raw/<id>/`; transforms run on Parquet copies. `tests/api/test_exit_gate.py` asserts the raw bytes are unchanged after rollback |
| T | Malformed or shifted rows corrupt the table | Rows with data beyond the header, or undecodable text, are quarantined with a reason (`engine/ingest/reader.py`, `tests/unit/test_w2_engine_a.py`); the CI evaluation benchmark requires 100% quarantine recall and precision (`scripts/evaluate_benchmark.py`) |
| D | Huge files or upload floods | 50 MB cap (`upload_max_mb`, 413 `FILE_TOO_LARGE`); 10 uploads per client per minute (`core/ratelimit.py`, `tests/unit/test_rate_limit.py`) |
| D | A crafted file crashes a job | The evaluation benchmark requires 0 crashes across the labelled adversarial cases, enforced in CI |
| I | Path traversal through stored-file keys | `_local_storage_file` in `main.py` resolves keys under the storage root only; `/api/v1/files/*` needs a signed-in user (`tests/api/test_auth_required.py`) |

## LLM path (`infer_rules`, `propose_steps`)

| STRIDE | Threat | Control (evidence) |
|---|---|---|
| T | Prompt injection: cell text instructs the model (FR-045) | `engine/guards/scanner.py` flags instruction-like cells across the whole table; flagged cells are never sent to the model and are listed on the Profile page (`tests/unit/test_m2_ai_path.py`; benchmark injection-flag rate at least 95% in CI) |
| T / E | The model proposes harmful actions | It can only choose from the fixed operation catalogue (an enum in the output schema); every AI step must validate and dry-run on the data before it enters a plan; a person approves every step; generated code is never executed (`merge_steps`, `tests/unit/test_m2_ai_path.py`) |
| I | Dataset contents leak to the model provider (GDPR, OQ-10) | Default off: schema + stats + at most 5 masked samples per column (`llm/redaction.py`); raw values only when an Administrator sets `allow_data_sharing` |
| I | The API key leaks | Keys are encrypted at rest with Fernet (`modules/model_config/crypto.py`) or held in OpenBao (`core/secrets.py`); never logged; gitleaks scans every push |
| R | AI failures hidden from users | `ai_status` / `ai_message` on profiles and plans, plus an `llm.failed` audit event (B2) |
| D | Provider throttling or outage stops cleaning | The deterministic rules always run; the gateway waits once on rate limits, then falls back with a visible banner (`llm/gateway.py`) |

## Export path (`POST /plans/{id}/exports`)

| STRIDE | Threat | Control (evidence) |
|---|---|---|
| T | Spreadsheet formula injection (`=HYPERLINK(...)`) | Formula-like text gets a leading `'` in XLSX and CSV (`neutralise_formulas`, `tests/unit/test_m2_ai_path.py`) |
| T | Exporting data that failed validation (FR-043) | 409 `EXPORT_BLOCKED_TESTS_FAILED` unless every generated test and reconciliation passed (`test_exit_gate.py`) |
| I | Export by a role that shouldn't have it | `data_engineer`, `administrator` and `viewer` only (`create_export/router.py`); download URLs need sign-in |
| R | Who exported or rolled back what | Every stage is written to the audit trail with the user (`test_exit_gate.py` checks the event list) |

## Sign-in path (`/api/v1/auth/*`)

| STRIDE | Threat | Control (evidence) |
|---|---|---|
| S | Password guessing on one account | 5 failures lock the account for 15 minutes (`users/features/login/service.py`, `test_login.py`) |
| S | Password spraying across accounts | 20 sign-ins per client per minute (`core/ratelimit.py`) |
| S | Forged or weak tokens | HS256 key of at least 32 bytes, and the `.env.example` placeholder is refused at startup (`tests/unit/test_config_jwt_secret.py`); with `AUTH_MODE=oidc`, Keycloak-issued RS256 tokens are checked against the realm's published signing keys |
| S | Stolen refresh token reused | Refresh tokens rotate on every use and live in an httpOnly, Secure, SameSite=Strict cookie; the refresh call also needs the `X-Requested-With` header (CSRF) |
| E | A viewer calls engineer-only routes | `require_roles` on every route; `test_route_auth_coverage.py` fails the build if a route has no auth |
| S | No second factor | With `AUTH_MODE=oidc`, Keycloak requires a TOTP authenticator app (see `docs/DEPLOYMENT.md`); local JWT mode has no MFA |

## Accepted risks (known, with the upgrade path)

| Risk | Why accepted | Upgrade |
|---|---|---|
| The audit log is append-only by API only (no update/delete routes); the database user could still edit rows | MVP scope | A separate DB role with INSERT/SELECT only on `audit.audit_events` |
| Rate-limit counters live in each API process | One API process in the demo | Redis counters when the API is scaled out |
| The public demo runs on a laptop through a Cloudflare quick tunnel, with seeded demo users | Demo only, no real data | The cloud VM + Caddy TLS runbook in `docs/DEPLOYMENT.md`; remove the demo users |
| OpenBao in dev mode (in-memory, root token) | Shows the integration only | Persistent storage, unseal keys and a scoped token policy |
| Local JWT mode has no MFA | Kept as the default so local dev and CI stay simple | Run with `AUTH_MODE=oidc` in any shared environment |
