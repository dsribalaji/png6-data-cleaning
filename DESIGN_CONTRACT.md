# DESIGN_CONTRACT.md — png6-data-cleaning

> Status: active. Every worker on this repo reads this file first and follows it
> exactly. If the contract and a worker's preference conflict, the contract wins.
> Change the contract only by editing this file and re-running the consistency pass.

## 1. Project tokens (use these exact names and numbers everywhere)

- Project: `png6-data-cleaning`. Team TITAN (ID NCS26GA-46). CodeStorm 2K26,
  30 Sep – 1 Oct 2026. Track: Generative AI & LLM Applications.
  Problem statement PNG6 — Agentic Data Cleaning Planner.
- Core loop, exact order: ingest → profile → infer → plan → approve → execute →
  verify → rollback.
- Reference dataset: `data/reference/VendorInvoices_uncleaned.xlsx` — one sheet,
  34 rows × 19 columns. That is 22 real data rows plus 12 blank padding rows
  (Excel rows 24–35) and 5 unnamed, fully-empty columns (O–S).
- Level-2 exit gate (verbatim from roadmap deck): "Invoice file goes from upload
  to validated export without manual steps." Output: 22 invoice rows,
  313 line items, gross total 154,292 matched. Rollback restores the original
  exactly.
- Observed issue labels (use verbatim): `supplier-variants-7-to-5`,
  `dollar-text-in-json`, `json-buried-line-items`, `float-artifacts`,
  `invalid-9char-gstin`, `missing-dates-pos`, `padding-rows`, `all-null-columns`,
  `redundant-total-price`.
- Screens (9, from the wireframe bundle): Datasets + upload popup, Profile
  report, Plan review, Execute + rollback, Generated tests, Quarantine banner,
  Audit trail, Model settings, Dataset detail.
- Hard constraints (from FRS intake): originals immutable, transforms run on a
  copy; byte-for-byte rollback; per-step loss estimates before execution; tests
  generated and run before/after; export withheld on test failure; quarantine for
  malformed rows; poisoned-cell flagging; model- and dataset-agnostic.

## 2. Stack (verbatim from the Tech Stack deck, September 2026)

Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic. PostgreSQL 16,
Redis (default — Valkey unresolved, see §6), MinIO. Celery on RabbitMQ,
Server-Sent Events. Polars, DuckDB, PyArrow. LiteLLM (Ollama / vLLM; provider
not locked). JWT + Argon2 for MVP auth. React + Vite + Tailwind CSS +
TanStack Query (Node.js builds the frontend; API types generated from FastAPI
OpenAPI). Docker Compose runs every service locally.

## 3. Directory layout (canonical — do not invent alternatives)

Per Backend.md (the build authority since 2026-09-30; the 9-slice brief is
superseded):

```
png6-data-cleaning/
  DESIGN_CONTRACT.md
  README.md
  AGENTS.md
  decision.md
  LICENSE
  .gitignore
  .env.example
  Makefile                        # docker compose -f deploy/docker-compose.yml ...
  backend/
    CLAUDE.md                     # copy of Backend.md — backend authority
    pyproject.toml · uv.lock · alembic.ini · Dockerfile
    src/planner/
      main.py                     # FastAPI factory; /api/v1, /api/docs, /health/live, /health/ready
      worker.py                   # Celery app; queues ingest, profile, plan, execute, validate, eval
      core/
        config.py · db.py · errors.py · security.py · outbox.py · events.py
        realtime.py · pagination.py · audit.py
        ports/                    # storage.py, llm.py, clock.py + adapters/
      modules/
        users/ datasets/ profiling/ planning/ execution/
        validation/ model_config/ audit/ evaluation/
          # each: models.py · public.py (ONLY import surface) · errors.py
          #       tasks.py · features/<use_case>/{router,service,schemas,test}.py
      engine/                     # pure data logic, no FastAPI/DB imports
        ingest/ profile/ infer/ ops/ loss/ tests_gen/ guards/
      llm/
        gateway.py                # ONLY file importing litellm
        cache.py · redaction.py · prompts/
    migrations/                   # Alembic versions
    tests/
      unit/ integration/ api/ fixtures/
  frontend/
    CLAUDE.md                     # copy of Frontend_PRD.md — frontend authority
    index.html · vite.config.ts · tailwind.config.ts · tsconfig.json
    src/
      main.tsx · app/ api/ auth/ features/ shared/ pages/ test/
    e2e/                          # Playwright
  contracts/events/*.schema.json  # generated from core/events.py
  deploy/
    docker-compose.yml            # postgres, redis, rabbitmq, minio, api, worker, beat,
                                  # frontend, prometheus, grafana (MVP per Backend.md)
  docs/                           # FRS, diagrams, ADRs
```

API conventions (Backend.md): base `/api/v1`, camelCase JSON, `application/problem+json`
errors, OpenAPI at `/api/docs`, SSE at `GET /api/v1/datasets/{id}/events`.
Tiebreak rule: where Backend.md and Frontend_PRD.md disagree, Backend.md wins —
the PRD cites it as the REST + SSE contract source. Resolved so far: approve is a
single call (`POST /plans/{id}/approve` enqueues test generation + execution);
exports are `POST /plans/{id}/exports`; real-time is SSE everywhere (the PRD's one
"SignalR" mention in S3 is a slip — SignalR is .NET and violates the no-Microsoft-stack
policy both docs state).

## 4. File ownership (coordinator assigns; no two workers write the same path)

- Worker 1 (scaffold): `backend/**`, `frontend/**`, `docker-compose.yml`,
  `.env.example`.
- Worker 2 (docs): `README.md`, `AGENTS.md`, `decision.md`, `LICENSE`,
  `.gitignore`, `docs/architecture/**`.
- Shared read-only input: `~/workspace/png6-intake/*.md` (requirements,
  stack-roadmap, data-plan) and this contract.

## 5. Conventions

- Docs in plain language; define every technical term on first use.
- `decision.md`: lowercase singular, newest first. Each entry: date, decider,
  decision, rationale, status (`active` / `superseded` / `proposed`).
- `docs/architecture/manifest.yaml`: `mode: brief`, `status: draft`.
  `brief-handoff.md` covers: what to build, in what order, what good looks
  like, what not to build. (Brief mode per the architecture-documenter skill;
  the full interview is deferred past the hackathon.)
- Links between docs use relative paths and must resolve.
- No secrets, keys, tokens, or credentials anywhere in the repo.
  `.env.example` carries placeholders only.
- Code: Python with type hints; Pydantic v2 schemas for all API input/output;
  one Docker image that starts as API, worker, or scheduler (per the deck).
- Never present a stub as working. Mark every unimplemented piece `not started`.

## 6. PROPOSED defaults (need SB / team approval; label PROPOSED in docs)

- P1: exception queue + labelled nulls instead of inventing values. The FRS
  leaves fill-vs-null open (OQ-12); the PowerBI guide's Step 4 invents
  `2025-09-01` and `MS-INDIA-SEP2025`. Default to the queue until the team
  decides.
- P2: Redis (not Valkey).
- P3: 5% loss limit, 50 MB upload, one role per user (deck defaults).

## 7. Out of scope for this scaffold

SAP posting, PO matching, dashboards, n8n changes, Keycloak / OpenBao,
Kubernetes, AI rule inference (Level 3). Level 2 is the deterministic core
flow only.

## 8. Consistency pass (coordinator runs this before push)

Layout matches §3; every doc link resolves; tokens and numbers match §1;
no stub presented as working; `decision.md` has the newest entry first.

## 9. Amendments

- 2026-09-30 (SB): the 9-slice build brief is **superseded**. `Backend.md` and
  `Frontend_PRD.md` (teammate-authored, copied into `backend/CLAUDE.md` and
  `frontend/CLAUDE.md`) are now the build authority. Consequences: the brief's
  Level-2 exclusions (no Prometheus/Grafana, no n8n folder poll, env-var-only
  secrets) and its dependency-approval rule are lifted; the docs' choices stand
  (Prometheus + Grafana in MVP compose, n8n folder poll beat task,
  Fernet-encrypted model credentials in DB, uv/asyncpg/boto3 and the listed
  test/tooling deps). The repo foundation is being reworked from the brief's
  `modules/{ingest…audit}` layout to the docs' `src/planner` layout (§3).
  Tiebreak: Backend.md wins over the PRD (the PRD cites it as the contract
  source) — approve is a single call, exports are `POST /plans/{id}/exports`,
  real-time is SSE everywhere (the PRD's "SignalR" in S3 is a slip).

## 10. LEVEL 2 BUILD — active build contract (2026-09-30, SB directive)

> Every worker on this build reads this section first and follows it exactly,
> plus backend/CLAUDE.md and frontend/CLAUDE.md (the build authorities;
> Backend.md wins ties). §7's "deterministic core only" is superseded for this
> build: Level 2 = the full MVP including Groq LLM inference.

### 10.1 Goal
A running system for the 9:30 PM Level-2 evaluation: upload the reference
workbook → profile → inferred rules → plan review with loss estimates →
approve → generated tests → execute → export, with rollback to v0 and a live
frontend (S1–S10 per frontend/CLAUDE.md). Backend: all 9 modules + engine +
LLM via Groq. "Everything up" = `uvicorn` API + Vite frontend on this VM in
local demo mode (§10.5), and `docker compose` for the full stack.

### 10.2 Worker slices and file ownership (no two workers write the same path)
- **W1 platform**: `src/planner/main.py`, `src/planner/worker.py`,
  `src/planner/core/**`, `src/planner/modules/users/**`,
  `src/planner/modules/datasets/**`, `migrations/**`, `contracts/events/**`
  (generated from `core/events.py`), `alembic.ini` edits.
- **W2 pipeline**: `src/planner/engine/**`, `src/planner/modules/profiling/**`,
  `src/planner/modules/planning/**`, `src/planner/modules/execution/**`,
  `src/planner/modules/validation/**`.
- **W3 intelligence**: `src/planner/llm/**`, `src/planner/modules/model_config/**`,
  `src/planner/modules/audit/**`, `src/planner/modules/evaluation/**`.
- **W4 frontend**: `frontend/**` (all screens S1–S10, CRMS theme, SSE client,
  RBAC, Playwright specs).
- Shared read-only: `backend/CLAUDE.md`, `frontend/CLAUDE.md`, this contract,
  `data/reference/VendorInvoices_uncleaned.xlsx`.

### 10.3 Cross-worker contracts (do not deviate)
- REST base `/api/v1`; OpenAPI UI `/api/docs`, JSON `/api/docs/openapi.json`.
- Health: `/api/v1/health/live`, `/api/v1/health/ready`.
- JSON camelCase; errors `application/problem+json`; lists
  `{ items, page, pageSize, total }`.
- SSE everywhere (the PRD's single "SignalR" mention is a wording error).
  Stream: `GET /api/v1/datasets/{id}/events`, messages
  `{ jobId, type, status, progressPct, message, planId? }`, 15 s heartbeat,
  `Last-Event-ID` replay from the `jobs` table.
- Module layout per backend/CLAUDE.md: `models.py`, `public.py` (ONLY import
  surface), `errors.py`, `tasks.py`, `features/<use_case>/{router,service,schemas,test_*.py}`.
  Modules import each other only via `public.py`; `core` imports no module;
  `engine/` has no FastAPI/DB imports (pure functions, Polars DataFrames).
- DB: one schema per module, `sqlalchemy.Uuid` PKs (works on Postgres and
  SQLite), `created_at`/`updated_at`, text CHECK enums, jsonb payloads →
  use `JSON` type (portable). Alembic migrations for all tables.
- Outbox: state change writes row + outbox event in one transaction; beat
  relay publishes to RabbitMQ; task completion publishes UI notification on
  Redis pub/sub channel `jobs:{datasetId}`.
- Ops catalogue (exact 8): `replace_value`, `fill_missing`, `drop_column`,
  `cast_type`, `derive_column`, `expand_nested`, `deduplicate`,
  `standardise_format`. Each: `validate`, `apply`, `inverse`, `estimate_loss`.
  LLM proposes JSON from this catalogue only; LLM-generated code is never
  executed.
- LLM: `llm/gateway.py` is the ONLY file importing `litellm`. Port:
  `LlmGateway.complete(task, payload, out) -> T`. Tasks: `infer_rules`,
  `propose_steps` only. Default model `openai/gpt-oss-120b` (verified live
  2026-09-30; `llama-3.3-70b-versatile` is retired on this account), override
  via model_config. In litellm the model id is prefixed: `groq/openai/gpt-oss-120b`. Key from `GROQ_API_KEY` env or the active
  `model_configs` row (Fernet). Data minimisation: schema + stats + ≤5 masked
  samples per column unless `allow_data_sharing`. Prompt-injection guard on
  cell samples. Redis cache `llm:{sha256(...)}`, 7-day TTL.
- Golden acceptance: 22 invoice rows + 313 line-item rows, gross total
  154,292 matched; 7 supplier variants → 5; rollback to v0 restores the
  original exactly.
- Frontend: React 19 + TS strict, Vite 6, Tailwind 3.4, CRMS tokens
  (Nunito Sans, `#fd6321` primary, `dark:` variants), React Router 7,
  TanStack Query 5, ky + refresh interceptor, Zustand (token in memory only,
  never localStorage), TanStack Table 8, RHF + Zod, openapi-typescript types
  generated from `/api/docs/openapi.json`. RBAC: forbidden nav/actions
  HIDDEN not disabled; direct URL → 403 page "You don't have access to this
  page." All strings in `shared/constants/messages.ts`. SSE via fetch +
  eventsource-parser with Bearer header.
- Fixture: the PRD's `Append_to_Reconciliation_Sheet.xlsx` does not exist;
  use `data/reference/VendorInvoices_uncleaned.xlsx` (and the backend test
  copy) for the golden test. Do not rename the immutable reference file.

### 10.4 Decisions locked for this build
- Approval: one call `POST /plans/{id}/approve` enqueues test generation +
  execution (no separate execute call from the UI).
- Exports: `POST /plans/{id}/exports` → `{ downloadUrl }` (pre-signed, 15 min);
  409 `EXPORT_BLOCKED_TESTS_FAILED` unless latest validation passed.
- n8n folder polling stays (spec requirement).
- No local AI model: Groq via LiteLLM only.

### 10.5 Local demo mode (this VM has no Docker)
Ports/adapters stay spec-shaped; adapters are env-selected:
- `DATABASE_URL` default (compose): `postgresql+asyncpg://…`; local demo:
  `sqlite+aiosqlite:///./planner.db`.
- `CELERY_BROKER_URL` default RabbitMQ; local demo: `CELERY_TASK_ALWAYS_EAGER=true`
  (tasks run inline; still idempotent, still write outbox + jobs rows).
- `REDIS_URL` default Redis; local demo: in-memory pub/sub adapter behind the
  realtime port (SSE still streams from the jobs table).
- `STORAGE_BACKEND=s3` (MinIO/boto3) default; local demo: `STORAGE_BACKEND=local`
  rooted at `./storage` with the same key layout (`raw/`, `snapshots/`,
  `exports/`, …).
- "Everything up" locally: `uvicorn planner.main:app` (port 8000) +
  `vite dev` (port 5173, proxy `/api` → 8000). Compose file unchanged and
  still the production path.

### 10.6 Working rules
- Coding agents do the code: `agy` (`~/.local/bin/agy -p`) first, OpenCode
  fallback. No unassigned manual background work.
- NEVER commit or push without SB's explicit approval. No secrets in the repo.
- Never present a stub as working; mark unfinished pieces `not started`.
- Python 3.12, `from __future__ import annotations`, ruff (line length 100),
  full type hints.

### 10.7 Consistency pass (coordinator runs before "done")
Layout matches backend/CLAUDE.md; `contracts/events/*.schema.json` regenerated
from `core/events.py`; frontend `api/schema.d.ts` regenerated from
`/api/docs/openapi.json`; every doc link resolves; golden test green;
`alembic upgrade head` clean on Postgres AND SQLite; `uvicorn` + `vite`
both serve; decision.md newest-first.
