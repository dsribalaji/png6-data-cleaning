# Agentic Data Cleaning Planner — Backend Specification (CLAUDE.md)

## Overview

**Project:** Agentic Data Cleaning Planner (PNG6)
**Scope of this file:** REST API, event-driven jobs, LLM integration, database and local infrastructure for the **MVP**.
**Traceability:** FRS v0.1 (FR-001 – FR-054, NFR-01 – NFR-09), High-Level Architecture, Level 1 DFD, Wireframes 1a–1l, Frontend PRD.
**Stack policy:** open-source only, no Microsoft stack. One backend language: **Python**.

### Why Python + FastAPI (decision record)
| Option | Verdict |
|---|---|
| **Python 3.12 + FastAPI** ✅ | The data work (Polars, DuckDB, PyArrow) and the model-agnostic LLM tooling (LiteLLM, Pydantic structured output) are Python-native. One language for API and workers means shared models, one test suite and one build. FastAPI gives async I/O, Pydantic validation and OpenAPI for free. |
| Node.js (NestJS / Fastify) | Strong for the API layer, but the dataframe and data-quality libraries are weaker. It would force a second Python service for the data work, which means two languages and duplicated contracts. |
| Go | Fast and small binaries, but few dataframe or LLM libraries. Too slow to build an MVP with. |

Node.js is still used for the **frontend** toolchain (Vite, React). See `Frontend PRD.md`.

---

## Tech Stack

| Layer | Choice | Licence |
|---|---|---|
| Language / packaging | **Python 3.12**, **uv** (deps, lockfile, workspaces) | PSF / MIT |
| API framework | **FastAPI** + **Uvicorn** (behind **Gunicorn** in containers) | MIT / BSD |
| Validation & settings | **Pydantic v2**, **pydantic-settings** | MIT |
| ORM & migrations | **SQLAlchemy 2.0 (async, `asyncpg`)**, **Alembic** | MIT |
| Database | **PostgreSQL 16** | PostgreSQL |
| Background jobs / events | **Celery 5** with **RabbitMQ 3.13** as broker, results in **Redis**; **transactional outbox** table + relay | BSD / MPL 2.0 |
| Real-time to UI | **Server-Sent Events** (`sse-starlette`), fed by **Redis pub/sub** | BSD |
| Cache | **Redis 7** (or **Valkey 8**, a drop-in open-source fork) | BSD |
| Object storage | **MinIO** (S3 API) via **boto3** | AGPL / Apache 2.0 |
| Data processing | **Polars**, **PyArrow**, **DuckDB**, **fastexcel** (XLSX read), **openpyxl** (XLSX write) | MIT / Apache 2.0 |
| Matching / parsing | **rapidfuzz** (near-duplicates), **python-dateutil** | MIT / BSD |
| LLM | **LiteLLM** (100+ providers incl. OpenAI, Groq, Anthropic, Ollama, vLLM) behind an internal `LlmGateway` port; **instructor** for Pydantic-typed outputs | MIT |
| Auth | **PyJWT**, **pwdlib[argon2]** (password hashing), rotating refresh tokens; **Keycloak** (Apache 2.0) planned for SSO/MFA post-MVP | MIT / Apache 2.0 |
| Secrets | **cryptography** (Fernet) for API keys at rest in the MVP; **OpenBao** (open-source Vault fork) post-MVP | Apache 2.0 / MPL 2.0 |
| Rate limiting | **slowapi** (Redis-backed) | MIT |
| Logging / telemetry | **structlog** (JSON), **OpenTelemetry** SDK + auto-instrumentation, **prometheus-client** | MIT / Apache 2.0 |
| Monitoring stack | **Prometheus**, **Grafana**, **Loki**, **Tempo**, **Alertmanager**, **Flower** (Celery) | Apache 2.0 / AGPL |
| Testing | **pytest**, **pytest-asyncio**, **httpx**, **testcontainers-python**, **hypothesis**, **schemathesis** (API fuzzing), **factory-boy** | MIT / BSD |
| Quality | **ruff** (lint + format), **mypy --strict**, **import-linter** (module boundaries), **pre-commit** | MIT / BSD |
| Containers | **Docker**, **docker compose** (MVP); **Kubernetes + Helm + KEDA** (Level 4) | Apache 2.0 |

---

## Architecture Style

- **Modular monolith** in one Python codebase with **two process types from the same image**:
  - `api`: FastAPI (REST + SSE)
  - `worker`: Celery workers, with separate queues `ingest`, `profile`, `plan`, `execute`, `validate`, `eval`
  - plus `beat` (scheduler: n8n folder polling, outbox relay)
- **Vertical slice per use case** inside each module: router, service, schemas and tests live together.
- **Ports & adapters** at the edges: storage, LLM, broker and clock are behind interfaces in `core/ports`, so tests use fakes.
- **Event-driven jobs:** a state change writes a row plus an **outbox** event in one DB transaction. The relay publishes to RabbitMQ and Celery tasks consume. On completion a task writes its results, emits the next outbox event, and publishes a UI notification on Redis `jobs:{datasetId}`.
- **Declarative transformation DSL:** the LLM *proposes* steps as JSON from a fixed operation catalogue, and only catalogue operations execute. **LLM-generated code is never executed.**
- **Module boundaries are enforced** by `import-linter`: a module may import another module only through its `public.py`, and `core` imports no module.

### Flow
```
React SPA ──REST──► FastAPI (api) ──tx: row + outbox──► PostgreSQL
    ▲                    │                                   │
    │◄──── SSE ◄── Redis pub/sub ◄─┐                 outbox relay (beat)
    │                              │                         ▼
    │                     Celery workers ◄──────────── RabbitMQ
    │                         │   │
    │                         │   └── LlmGateway (LiteLLM) ──► any provider
    │                         ▼
    │                     MinIO (Parquet / XLSX / CSV / JSON)
```

### Job chain (event → task → event)
| Trigger event | Celery task (queue) | Emits | FR |
|---|---|---|---|
| `dataset.uploaded` | `ingest_dataset` (ingest) | `dataset.ingested` | FR-001 – FR-005, FR-044 |
| `dataset.ingested` | `profile_dataset` (profile) | `dataset.profiled` | FR-006 – FR-012 |
| `dataset.profiled` | `infer_rules` (profile) | `rules.inferred` | FR-013 – FR-020 |
| `plan.requested` | `generate_plan` (plan) | `plan.generated` | FR-021 – FR-030 |
| `plan.approved` | `generate_tests` (validate) → `execute_plan` (execute) | `plan.step_executed` × n → `plan.executed` | FR-032, FR-035, FR-039 |
| `plan.executed` | `run_validation` (validate) | `validation.completed` | FR-040 – FR-043 |
| `rollback.requested` | `rollback_plan` (execute) | `rollback.completed` | FR-033 – FR-034 |
| `evaluation.requested` | `run_evaluation` (eval) | `evaluation.completed` | FR-047 |
| any failure after retries | — | `job.failed` | NFR-07 |

**Rules:**
- Task args are IDs only (`dataset_id`, `plan_id`, `job_id`). File contents never go in messages.
- Every task is **idempotent**: it takes a row lock on `jobs` and exits if the job is already `succeeded`.
- `acks_late=True`, `task_reject_on_worker_lost=True`. Retries use exponential backoff (10s, 60s, 5m, max 3), then the dead-letter queue and `job.failed`.
- Tasks that call the LLM have `soft_time_limit=120`. Execute tasks: `soft_time_limit=900`.
- Event names and payloads are defined once in `core/events.py` (Pydantic) and exported to `contracts/events/*.schema.json` for the frontend and docs.

### Real-time (SSE)
`GET /api/v1/datasets/{id}/events` (auth required) streams `job.status` messages `{ jobId, type, status, progressPct, message, planId? }`. A heartbeat is sent every 15 s. The browser reconnects with `Last-Event-ID`, and the server replays from the `jobs` table.

---

## Repository Structure

```
data-cleaning-planner/
├── backend/
│   ├── CLAUDE.md                          # this file
│   ├── pyproject.toml · uv.lock · alembic.ini · Dockerfile
│   ├── src/planner/
│   │   ├── main.py                        # FastAPI app factory, routers, middleware, exception handlers
│   │   ├── worker.py                      # Celery app, queues, beat schedule
│   │   ├── core/
│   │   │   ├── config.py                  # pydantic-settings
│   │   │   ├── db.py                      # async engine, session dependency, Base (snake_case naming)
│   │   │   ├── errors.py                  # AppError(code, message, status) + handlers → application/problem+json
│   │   │   ├── security.py                # JWT, password hashing, current_user, require_roles()
│   │   │   ├── outbox.py                  # outbox model, add_event(), relay task
│   │   │   ├── events.py                  # event names + Pydantic payloads (contract source)
│   │   │   ├── realtime.py                # Redis pub/sub publisher, SSE endpoint helper
│   │   │   ├── pagination.py · audit.py   # Page[T]; record_audit() used by every module
│   │   │   └── ports/                     # storage.py, llm.py, clock.py (protocols) + adapters/
│   │   ├── modules/
│   │   │   ├── users/                     # auth, invite, roles (wireframes 1a, 1c, 1k)
│   │   │   ├── datasets/                  # upload, list, detail, quarantine, n8n folder poll (FR-001 – FR-005, FR-044)
│   │   │   ├── profiling/                 # column stats, flags, inferred rules (FR-006 – FR-020)
│   │   │   ├── planning/                  # plans, steps, decisions, loss, approval (FR-021 – FR-031)
│   │   │   ├── execution/                 # run, versions, rollback, exports (FR-032 – FR-038)
│   │   │   ├── validation/                # test generation, runs, reconciliation, export gate (FR-039 – FR-043)
│   │   │   ├── model_config/              # provider/model/credential, connection test (FR-048 – FR-049)
│   │   │   ├── audit/                     # append-only log, query, CSV export (FR-051 – FR-052)
│   │   │   └── evaluation/                # benchmark sets and runs (FR-047)
│   │   ├── engine/                        # pure data logic, no FastAPI/DB imports
│   │   │   ├── ingest/                    # xlsx/csv → parquet, quarantine rules
│   │   │   ├── profile/                   # stats, semantic types, nested JSON, numeric-as-text
│   │   │   ├── infer/                     # entity groups, arithmetic rules, keys, 1:N
│   │   │   ├── ops/                       # operation catalogue: apply / inverse / estimate_loss
│   │   │   ├── loss/                      # per-step + cumulative loss
│   │   │   ├── tests_gen/                 # declarative checks → runner + pytest export
│   │   │   └── guards/                    # prompt-injection scan, sparsity, size limits
│   │   └── llm/
│   │       ├── gateway.py                 # LlmGateway → LiteLLM adapter (only file importing litellm)
│   │       ├── cache.py · redaction.py
│   │       └── prompts/                   # infer_rules.v1.md, propose_steps.v1.md
│   ├── migrations/                        # Alembic versions
│   └── tests/
│       ├── unit/ (engine, ops inverse property tests)
│       ├── integration/ (testcontainers: postgres, rabbitmq, redis, minio)
│       ├── api/ (httpx + schemathesis)
│       └── fixtures/Append_to_Reconciliation_Sheet.xlsx · benchmarks/ (adversarial files)
├── frontend/                              # React + Vite, see Frontend PRD.md
├── contracts/events/*.schema.json         # generated from core/events.py
├── deploy/
│   ├── docker-compose.yml                 # postgres, redis, rabbitmq, minio, api, worker, beat, frontend, otel, prometheus, grafana
│   └── helm/                              # Level 4: api/worker Deployments, HPA (api), KEDA ScaledObject (worker, RabbitMQ queue length)
└── docs/                                  # FRS, diagrams, ADRs
```

### Module layout (every module follows this)
```
modules/planning/
├── models.py              # SQLAlchemy models (schema "planning")
├── public.py              # the ONLY import surface for other modules
├── errors.py              # PlanningErrors: static AppError instances
├── tasks.py               # Celery tasks for this module
└── features/
    ├── generate_plan/     { router.py, service.py, schemas.py, test_generate_plan.py }
    ├── decide_step/       { router.py, service.py, schemas.py, test_decide_step.py }
    ├── approve_plan/      { ... }
    └── get_plan/          { ... }
```
- `router.py`: FastAPI `APIRouter`. It handles HTTP only (parse, auth dependency, call service, map response).
- `service.py`: the use case, as plain async functions taking `(session, actor, input)` and returning a schema. It raises `AppError` for business failures.
- `schemas.py`: Pydantic request/response models. The API uses camelCase via `alias_generator`.

---

## Database (PostgreSQL 16)

- One database `planner`, **one schema per module**, snake_case via SQLAlchemy `naming_convention`.
- PKs are `uuid` (UUIDv7 generated in app). Every table has `created_at timestamptz NOT NULL DEFAULT now()`. Mutable tables have `updated_at` plus an optimistic `version_id` (SQLAlchemy `version_id_col`).
- Enum-like columns are `text` with a `CHECK` constraint. Flexible payloads are `jsonb` with `schema_version`.
- Dataset contents live **only** in MinIO as Parquet, never in Postgres.

```
users.users                 id, email citext UNIQUE, first_name, last_name, password_hash, status CHECK(invited|active|deactivated),
                            failed_logins, locked_until, last_login_at
users.user_roles            user_id FK UNIQUE, role CHECK(data_engineer|administrator|auditor|viewer)   -- one role per user (OQ-21)
users.refresh_tokens        id, user_id FK, token_hash, family_id, expires_at, revoked_at
users.invites               id, email, role, token_hash, expires_at, accepted_at

datasets.datasets           id, name UNIQUE, source CHECK(upload|n8n_folder), file_name, row_count, column_count,
                            status CHECK(profiling|profiled|plan_ready|approved|executed|tests_failed|rolled_back|failed),
                            raw_object_key, ingested_at, uploaded_by FK
datasets.quarantine_records id, dataset_id FK, row_ref, reason
datasets.jobs               id, dataset_id FK, plan_id NULL, type, status CHECK(queued|running|succeeded|failed),
                            progress_pct, error_code, error_message, celery_task_id, started_at, finished_at

profiling.column_profiles   id, dataset_id FK, column_name, ordinal, physical_type, semantic_type, null_count, null_pct,
                            distinct_count, min_value, max_value, mean_value, flags text[]
profiling.inferred_rules    id, dataset_id FK, rule_type CHECK(entity_group|arithmetic|primary_key|one_to_many|semantic_type|cross_field_fill),
                            columns text[], expression jsonb, confidence numeric(3,2) CHECK (confidence BETWEEN 0 AND 1),
                            evidence_rows jsonb, prompt_version

planning.plans              id, dataset_id FK, status CHECK(proposed|in_review|approved|rejected|superseded),
                            total_estimated_loss numeric(6,3), loss_threshold numeric(6,3), approved_by, approved_at
planning.plan_steps         id, plan_id FK, step_no, operation CHECK(replace_value|fill_missing|drop_column|cast_type|
                            derive_column|expand_nested|deduplicate|standardise_format), parameters jsonb, rationale,
                            confidence, decision CHECK(pending|accepted|edited|rejected), decision_reason, decided_by, decided_at,
                            UNIQUE(plan_id, step_no)
planning.loss_estimates     step_id PK FK, rows_affected, columns_affected, cells_affected, estimated_loss numeric(6,3)

execution.pipeline_versions id, plan_id FK, version_no, step_id NULL (v0 = original), snapshot_object_key,
                            inverse_operation jsonb, executed_at, executed_by, UNIQUE(plan_id, version_no)
execution.rollbacks         id, plan_id FK, from_version_no, to_version_no, reason CHECK(length BETWEEN 10 AND 500),
                            requested_by, completed_at
execution.exports           id, plan_id FK, version_no, format CHECK(xlsx|csv|pipeline), object_key, exported_by

validation.test_cases       id, plan_id FK, type CHECK(unit|integration), target_step_id NULL, name, definition jsonb
validation.test_runs        id, test_case_id FK, version_no, phase CHECK(before|after), result CHECK(passed|failed|error), detail, run_at
validation.reconciliations  id, plan_id FK, version_no, check_name, source_value, output_value, ok

model_config.model_configs  id, provider, model, endpoint_url NULL, credential_ciphertext, credential_last4,
                            allow_data_sharing bool DEFAULT false, is_active bool, updated_by
                            -- UNIQUE (is_active) WHERE is_active

audit.audit_events          id, occurred_at, user_id NULL, user_role, event_type, object_type, object_id, details jsonb, correlation_id
                            -- append-only: app DB role has INSERT, SELECT only; BRIN index on occurred_at

evaluation.benchmark_sets   id, name, description, object_keys text[]
evaluation.evaluation_runs  id, benchmark_set_id FK, model_config_id FK, scores jsonb, started_at, finished_at

public.outbox               id, event_type, payload jsonb, created_at, published_at NULL   -- index on (published_at) WHERE published_at IS NULL
```

**Object storage** (bucket `planner`): `raw/{datasetId}/{file}` (write-once, FR-004) · `snapshots/{planId}/v{n}.parquet` · `quarantine/{datasetId}.parquet` · `exports/{planId}/v{n}/{table}.{xlsx|csv}` · `pipelines/{planId}/v{n}.json` · `tests/{planId}/test_pipeline.py`.

**Reversibility (FR-032 – FR-034):** a Parquet snapshot is written for each executed step, and the `inverse_operation` is recorded. Rollback restores the snapshot. Hypothesis property tests check that `inverse(apply(df)) == df` for every operation. v0 is never deleted.

---

## LLM Integration

- **One port:** `LlmGateway.complete(task: str, payload: BaseModel, out: type[T]) -> T`. `llm/gateway.py` is the only file that imports `litellm` (enforced by import-linter; FR-048).
- **Config:** the active `model_configs` row is read on each task and the key decrypted in memory. Keys are never logged; a structlog processor redacts `api_key`, `authorization` and `password` (NFR-01).
- **Structured output:** each task has a Pydantic output model (via instructor). Invalid output gets 1 repair retry, then the rule/step is marked low-confidence and deterministic heuristics are used.
- **LLM tasks:** only `infer_rules` and `propose_steps`. Profiling, loss, execution and tests are **deterministic**.
- **Data minimisation (NFR-02, OQ-10):** by default the model sees schema + stats + ≤ 5 masked sample values per column. Raw values are sent only if `allow_data_sharing = true`.
- **Prompt-injection guard (FR-045):** cell values are sent as quoted JSON inside a delimited block. `engine/guards/injection.py` flags instruction-like cells, and flagged cells are excluded from samples.
- **Cache:** Redis key `llm:{sha256(provider|model|prompt_version|payload)}`, TTL 7 days.
- **Local / offline option:** any **Ollama** or **vLLM** endpoint works via LiteLLM, which keeps the stack fully open source end to end if needed.

### Operation catalogue (FR-022)
Each op implements `validate(params, schema)`, `apply(df) -> df`, `inverse(before, after) -> InverseOp`, `estimate_loss(df) -> LossEstimate`.

| Op | Reference-dataset example |
|---|---|
| `replace_value` | 7 supplier name variants → 5 canonical names |
| `fill_missing` | PO blanks → "Not Assigned" |
| `drop_column` | `customer_vat_number` (100% null) |
| `cast_type` | strip `$` and `,` → Decimal |
| `derive_column` | `vat_amount = subtotal_with_vat − subtotal_without_vat` (expression AST parsed by a whitelist, no `eval`) |
| `expand_nested` | `line_items` JSON → `LineItems` table keyed by `invoice_number` |
| `deduplicate` | exact duplicate invoice rows |
| `standardise_format` | dates → ISO-8601 |

---

## REST API (MVP)

Base `/api/v1`. JSON with camelCase fields. Errors are `application/problem+json` `{ type, title, status, detail, code, errors? }`. Lists return `{ items, page, pageSize, total }`. OpenAPI at `/api/docs`, which the frontend uses to generate types.

| Method & route | Roles | FR |
|---|---|---|
| `POST /auth/login` · `POST /auth/refresh` · `POST /auth/logout` · `GET /auth/me` · `POST /auth/invites/{token}/accept` | public / any | NFR-03 |
| `GET /users` · `POST /users/invites` · `PATCH /users/{id}/role` · `POST /users/{id}/deactivate` | administrator | 1k |
| `POST /datasets` (multipart) · `GET /datasets` · `GET /datasets/{id}` · `GET /datasets/{id}/quarantine` | data_engineer / any | FR-001 – FR-005, FR-044 |
| `GET /datasets/{id}/events` (SSE) | any | real-time |
| `GET /datasets/{id}/profile` · `GET /datasets/{id}/rules` | any | FR-006 – FR-020 |
| `POST /datasets/{id}/plans` · `GET /plans/{id}` | data_engineer / any | FR-021 – FR-030 |
| `PATCH /plans/{id}/steps/{stepId}` · `POST /plans/{id}/approve` | data_engineer | FR-027, FR-039 |
| `GET /plans/{id}/versions` · `POST /plans/{id}/rollback` | any / data_engineer | FR-032 – FR-034 |
| `GET /plans/{id}/validation` | any | FR-039 – FR-042 |
| `POST /plans/{id}/exports` → `{ downloadUrl }` (pre-signed, 15 min) | data_engineer, viewer | FR-036 – FR-037, FR-043 |
| `GET /model-config` · `PUT /model-config` · `POST /model-config/test` · `GET /model-config/providers` | administrator | FR-049 |
| `GET /audit-events` · `GET /audit-events/export` | auditor (administrator: GET only) | FR-051 – FR-052 |
| `POST /evaluations` · `GET /evaluations` · `GET /evaluations/{id}` | data_engineer, administrator | FR-047 |
| `GET /config/upload` | any | limits for the UI |
| `GET /health/live` · `GET /health/ready` · `GET /metrics` | public / internal | NFR-08 |

`POST /plans/{id}/approve` also enqueues test generation and execution, so the UI makes a single call.

**Export gate (FR-043):** `POST /exports` returns `409 EXPORT_BLOCKED_TESTS_FAILED` unless the latest `validation.completed` for that version passed.

---

## Authentication & Authorization

- **Access token:** JWT (HS256 in MVP, RS256 once Keycloak is added), 15 min, claims `sub`, `role`, `jti`. It is returned in the body and kept in memory by the SPA.
- **Refresh token:** 7 days, rotated on every use with reuse detection (`family_id`: reuse revokes the family). Sent as an **httpOnly, Secure, SameSite=Strict** cookie scoped to `/api/v1/auth`.
- **Passwords:** Argon2id via pwdlib, 12–128 chars. **Lockout:** 5 failures → 15 min (assumed, OQ-16).
- **No self-registration.** Only Administrator invites (24 h token).
- **Authorization:** FastAPI dependency `require_roles(Role.data_engineer, …)` on every router. Roles are `data_engineer | administrator | auditor | viewer` (wireframe 1c).
- **CSRF:** access tokens are sent in the `Authorization` header, not cookies. The refresh endpoint also requires the `X-Requested-With` header.
- **Post-MVP:** Keycloak (OIDC) for SSO and MFA (OQ-17, OQ-19). `security.py` hides the token verifier behind `TokenVerifier`, so the switch doesn't touch features.
- Every login, success or failure, is written to the audit log (FR-051).

---

## Code Conventions

- Python 3.12, `from __future__ import annotations`, full type hints, `mypy --strict` clean.
- **ruff** for lint and format (line length 100). Imports sorted by ruff.
- **Async everywhere in the API** (`async def`, `AsyncSession`). Celery tasks are sync wrappers that call async services via `asyncio.run`, or use sync sessions in the engine.
- **Pydantic models** for all I/O. **SQLAlchemy models** never leave a module; map them to schemas in `service.py`.
- **Errors:** raise `AppError` instances defined in `modules/*/errors.py`. The global handler maps them to problem+json. Never return raw 500s for business rules.
- **Transactions:** one `AsyncSession` per request, committed at the end of the service. Outbox events are added in the same session.
- **No global state** in `engine/`. Functions take and return `polars.DataFrame` plus typed params.
- Naming: packages and files are `snake_case`, classes `PascalCase`, API fields camelCase (aliases), DB columns snake_case.

### We use
Vertical slices · ports & adapters · transactional outbox · idempotent tasks · Pydantic everywhere · import-linter boundaries · property tests for ops.

### We don't use
❌ Django/DRF (too heavy for this API) · ❌ ORM models in API responses · ❌ executing LLM-generated code · ❌ file contents in messages · ❌ Microsoft/.NET/Azure-only components · ❌ modules importing each other's internals.

---

## Error Catalogue

| Code | HTTP | Message (shown in UI) |
|---|---|---|
| `INVALID_CREDENTIALS` | 401 | Email or password is incorrect. |
| `ACCOUNT_LOCKED` | 423 | Your account is locked. Try again in 15 minutes. |
| `ACCOUNT_INACTIVE` | 403 | Your account is inactive. Contact an Administrator. |
| `USER_EXISTS` | 409 | This user already exists. |
| `DATASET_NAME_TAKEN` | 409 | A dataset with this name already exists. |
| `UNSUPPORTED_FILE_TYPE` | 400 | Only .xlsx or .csv files can be uploaded. |
| `FILE_TOO_LARGE` | 413 | The file is larger than {limit} MB. (default 50 MB, OQ-09) |
| `PLAN_NOT_FULLY_DECIDED` | 409 | Decide every step before approving the plan. |
| `REASON_REQUIRED` | 400 | Enter a reason of at least 10 characters. |
| `EXPORT_BLOCKED_TESTS_FAILED` | 409 | Export is blocked because 1 or more tests failed. |
| `MODEL_CONNECTION_FAILED` | 422 | Could not reach the provider. Check the key and endpoint. |
| `JOB_ALREADY_RUNNING` | 409 | A job of this type is already running for this item. |

---

## Testing

- **Naming:** `test_<use_case>__<scenario>__<expected>` (e.g. `test_approve_plan__pending_step__returns_409`).
- **Unit:** `engine/` and `ops/` with hypothesis (inverse property, loss never negative).
- **Golden test** on the reference dataset: 22 rows → 22 InvoiceSummary + 313 LineItems, gross total 154,292, 7 supplier names → 5.
- **Integration:** testcontainers for Postgres, RabbitMQ, Redis and MinIO. Celery runs with `task_always_eager=False` to exercise real queues.
- **API:** httpx `AsyncClient` per slice, plus schemathesis against `/api/docs/openapi.json` in CI.
- **Adversarial (FR-047):** `tests/fixtures/benchmarks/` has malformed rows, injected instructions and 95%-sparse columns. A task crashing instead of quarantining fails CI.
- **Coverage gate:** 80% on `engine/` and `modules/*/features`.

---

## Local Development

```bash
cp .env.example .env
docker compose -f deploy/docker-compose.yml up -d postgres redis rabbitmq minio
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn planner.main:app --reload --port 8000        # http://localhost:8000/api/docs
uv run celery -A planner.worker worker -Q ingest,profile,plan,execute,validate,eval -l info
uv run celery -A planner.worker beat -l info
```

Migrations: `uv run alembic revision --autogenerate -m "<message>"` then `uv run alembic upgrade head`.

### .env (excerpt)
```
DATABASE_URL=postgresql+asyncpg://planner:planner@localhost:5432/planner
RABBITMQ_URL=amqp://guest:guest@localhost:5672//
REDIS_URL=redis://localhost:6379/0
S3_ENDPOINT=http://localhost:9000
S3_BUCKET=planner
S3_ACCESS_KEY=minio
S3_SECRET_KEY=minio123
JWT_SECRET=<32+ chars>
JWT_ACCESS_MINUTES=15
JWT_REFRESH_DAYS=7
FERNET_KEY=<generated>
UPLOAD_MAX_MB=50
LOSS_THRESHOLD_DEFAULT=0.05
N8N_FOLDER_POLL_MINUTES=5
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
CORS_ORIGINS=http://localhost:5173
```

---

## MVP Boundaries

**In:** the REST API above, SSE progress, Celery/RabbitMQ job chain, one active model config, XLSX/CSV upload, n8n folder polling, docker compose deployment with Prometheus + Grafana.
**Out (later levels):** Kubernetes/Helm/KEDA autoscaling and read replicas (Level 4), Keycloak SSO/MFA, OpenBao, multi-role users, dashboards (FR-053), n8n workflow changes (FR-054).

## Open Questions Affecting the Backend
OQ-03 approval gate · OQ-04 loss threshold (5% assumed) · OQ-09 max file size (50 MB assumed) · OQ-10 data sharing with providers · OQ-11 providers at launch · OQ-16 lockout (5 / 15 min assumed) · OQ-21 one role per user (assumed) · OQ-23 loss unit (% of cells assumed).
