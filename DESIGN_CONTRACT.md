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

```
png6-data-cleaning/
  DESIGN_CONTRACT.md
  README.md
  AGENTS.md
  decision.md
  LICENSE
  .gitignore
  .env.example
  docker-compose.yml
  backend/
    Dockerfile
    pyproject.toml
    app/
      main.py
      api/          # routers: datasets, profile, plans, execute, tests, audit, auth
      core/         # config, security (jwt), events (sse)
      models/       # sqlalchemy 2 models
      schemas/      # pydantic v2 schemas
      services/     # profiler, planner, loss_estimator, executor, tester, rollback, quarantine
      workers/      # celery tasks
    alembic/
    tests/
  frontend/
    Dockerfile
    package.json
    vite.config.ts
    tailwind.config.js
    src/
      main.tsx
      App.tsx
      api/          # tanstack query hooks, generated openapi types
      components/
      pages/        # Datasets, Profile, PlanReview, Execute, Tests, Quarantine, Audit, ModelSettings, DatasetDetail
  data/
    reference/
      VendorInvoices_uncleaned.xlsx
  docs/
    architecture/
      manifest.yaml
      brief-handoff.md
```

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
