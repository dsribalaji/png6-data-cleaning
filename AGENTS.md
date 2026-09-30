# AGENTS.md — png6-data-cleaning (Team TITAN, NCS26GA-46)

Repo-level operating instructions for any coding agent working here. Before writing anything, read `DESIGN_CONTRACT.md` (the binding contract) and the shared intake files under `~/workspace/png6-intake/` (requirements.md, stack-roadmap.md, data-plan.md). If a contract rule and your preference conflict, the contract wins.

## The stack

Declared by the Tech Stack deck (September 2026) as the open-source MVP stack:

- **Python 3.12** — the programming language; it runs both the API (application programming interface — the HTTP endpoints other programs call) and the background workers.
- **FastAPI** — the Python web framework that serves the REST API (REST: an API style where each resource is an HTTP URL).
- **Pydantic v2** — validation and structured-output library; every API request and response body is validated against a Pydantic schema (a defined shape of data).
- **SQLAlchemy 2** — the Python database-access library.
- **Alembic** — the database migration tool (migrations are versioned scripts that change the database schema safely over time).
- **PostgreSQL 16** — the relational database, the system of record for plans, versions, and audit events.
- **Redis** — the in-memory cache (later used for profiles, query results, model responses). The deck lists "Redis (or Valkey)"; Redis is the PROPOSED default (contract §6, P2) until the team decides.
- **MinIO** — the S3-compatible object storage where raw and cleaned dataset files live.
- **Celery on RabbitMQ** — the background job system (Celery: the Python task queue; RabbitMQ: the message broker that carries the jobs). Jobs are chained with retries and a dead-letter queue (a holding area for jobs that repeatedly fail).
- **SSE (Server-Sent Events)** — pushes each job's status to the browser so users never need to refresh.
- **Polars, DuckDB, PyArrow** — the Python data libraries used for profiling and cleaning large columnar data.
- **LiteLLM** — a provider-independent interface for calling large language models (LLMs — the AI used for semantic inference). Connects to any provider, including self-hosted Ollama or vLLM; the provider is not locked. AI-driven rule inference is Level 3, not Level 2.
- **JWT + Argon2** — MVP sign-in (JWT: JSON Web Token, a signed credential passed with each request; Argon2: the password-hashing algorithm used to store passwords safely).
- **React + Vite + Tailwind CSS + TanStack Query** — the frontend: React is the UI (user interface) library, Vite is the build tool, Tailwind CSS is the styling framework, TanStack Query is the data-fetching library. Node.js is used to build the frontend; API types are generated from FastAPI's OpenAPI spec (OpenAPI: a machine-readable description of the API).
- **Docker Compose** — runs every service locally for the MVP. Per the deck: "One Docker image starts as API, worker or scheduler."

Defaults (PROPOSED until the team approves, contract §6, P3): 5% loss limit, 50 MB upload, one role per user.

## How to run it

```bash
docker compose up
```

One Docker image (a packaged, runnable snapshot of the app and its dependencies) starts as API, worker, or scheduler.

## Where code lives

Per the canonical layout in `DESIGN_CONTRACT.md` §3 (Backend.md + Frontend_PRD.md
are the build authority since 2026-09-30; the 9-slice brief is superseded —
this section was updated to match; the contract wins on any conflict):

- `backend/` — `CLAUDE.md` (copy of Backend.md), `src/planner/` (the Python
  service: `main.py`, `worker.py`, `core/`, `modules/`, `engine/`, `llm/`),
  `migrations/` (Alembic), `tests/` (unit, integration, api, fixtures).
  Modules: users, datasets, profiling, planning, execution, validation,
  model_config, audit, evaluation. Each module exposes only `public.py` to
  other modules (import-linter); `llm/gateway.py` is the only file importing
  litellm.
- `frontend/` — `CLAUDE.md` (copy of Frontend_PRD.md), feature-sliced SPA
  (`src/app`, `src/api`, `src/auth`, `src/features`, `src/shared`), `e2e/`
  (Playwright).
- `contracts/events/` — JSON schemas generated from `core/events.py`.
- `deploy/docker-compose.yml` — postgres, redis, rabbitmq, minio, api, worker,
  beat, frontend, prometheus, grafana.
- `data/reference/` — the untouched reference dataset
  (`VendorInvoices_uncleaned.xlsx`).
- `docs/` — FRS, diagrams, ADRs.

API conventions: base `/api/v1`, camelCase JSON, problem+json errors, OpenAPI at
`/api/docs`, SSE at `GET /api/v1/datasets/{id}/events`. Do not invent
alternative directories; the contract forbids it.

## Conventions

- Python with type hints (declared types on function arguments and returns).
- Pydantic v2 schemas for all API input/output.
- Honest TODO markers: a `TODO:` comment must state what is missing and what "done" looks like.
- Never present a stub (a placeholder that does nothing) as working. Mark every unimplemented piece `not started`.
- Docs are in plain language; define every technical term on first use.
- The Level-2 exit gate is quoted verbatim in `README.md`; keep its wording and numbers exact everywhere.

## What not to do

- No secrets, keys, tokens, or credentials anywhere in the repo. `.env.example` carries placeholders only.
- Do not modify `data/reference/VendorInvoices_uncleaned.xlsx` — the original is immutable by design (FRS FR-004).
- Do not commit or push; the coordinator runs the consistency pass (`DESIGN_CONTRACT.md` §8) and commits when all workers are done.
- Do not build anything in the out-of-scope list: SAP posting, dashboards, n8n changes, Keycloak/OpenBao, Kubernetes, AI rule inference (Level 3). See `docs/architecture/brief-handoff.md`.

## File ownership

Worker 1 (scaffold) owns: `backend/**`, `frontend/**`, `docker-compose.yml`, `.env.example`.
Worker 2 (docs) owns: `README.md`, `AGENTS.md`, `decision.md`, `LICENSE`, `.gitignore`, `docs/architecture/**`.
Shared read-only input: `~/workspace/png6-intake/*.md` and `DESIGN_CONTRACT.md`.
