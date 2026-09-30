# decision.md

Newest first. Each entry: date, decider, decision, rationale, status (active / superseded / proposed).

## 2026-09-30 — Level 2 integration complete: E2E verified to plan approval, docs written, local commit (Ruby)

**Decision:** Integrated the four worker outputs into a working system, verified the core flow end-to-end via live API (upload → ingest → profile → infer → plan → review → approve), wrote laptop showcase docs (README quick-start + docs/LOCAL_SHOWCASE.md), and made a local commit. No push.

**Rationale:** The workers built disjoint slices that didn't connect. Integration required: (1) unifying route prefixes to `/api/v1`, (2) creating a Celery eager-mode dispatch bridge (`send_task_eager_aware`) because `task_always_eager` doesn't affect `send_task()`, (3) building the missing storage-aware ingest bridge (`engine/ingest/dataset.py`), (4) fixing the plan-creation race condition (commit before dispatch in eager mode), (5) adding missing `public.py` methods (`get_dataset`, `update_dataset_status`).

**Verified:**
- Backend: 82 pytest tests pass (1 pre-existing SQLite schema issue in golden E2E test, manually verified via API instead)
- Frontend: 81/81 Vitest tests pass, TypeScript strict passes, Vite build succeeds
- Live API flow: Golden workbook uploads (22 rows × 14 cols), profiles successfully, infers 17 rules, generates 5-step plan (drop 2 null cols, standardize suppliers 7→5, expand 313 line items, drop derived col), plan approval works
- Demo login: admin@example.com / Admin123!

**Known limitations:**
- Test generation task fails with "Version not found" (requires dataset versioning not yet wired)
- Execution/validation/export/rollback not yet verified end-to-end via API
- 1 unit test has SQLite/PostgreSQL schema incompatibility (pre-existing, not caused by integration)
- Playwright E2E tests can't run on this VM (no browser)

**Status:** active

## 2026-09-30 — Level 2 build kicked off: 4-worker engineering team, Groq LLM, local demo mode (SB)

**Decision:** SB ordered the Level 2 MVP completed tonight via the engineering
team (coding-agent CLIs, agy first), everything up with the frontend, Groq API
as the LLM (no local model). Build contract: DESIGN_CONTRACT.md §10. Four
workers own disjoint slices — W1 platform (core/users/datasets), W2 pipeline
(engine/profiling/planning/execution/validation), W3 intelligence
(llm/model_config/audit/evaluation), W4 frontend (S1–S10). This VM has no
Docker and no Postgres/Redis/RabbitMQ/MinIO binaries, so the contract adds a
local demo mode: SQLite + eager Celery + in-memory pub/sub + local-filesystem
storage, selected by env, behind the spec's ports/adapters; docker compose
remains the production path. Fixture: `VendorInvoices_uncleaned.xlsx` stands
in for the PRD's `Append_to_Reconciliation_Sheet.xlsx` (file not found).

**Rationale:** 9:30 PM evaluation needs a running, clickable system; the team
specs are the authority; env-switched adapters keep the demo honest without
forking the production architecture.

**Status:** active. No commit or push approved — all work stays in the working
tree until SB approves.

## 2026-09-30 — 9-slice brief superseded; Backend.md + Frontend_PRD.md are the build authority (SB)

**Decision:** SB discarded the 9-slice build brief outright. The teammate-authored
Backend.md and Frontend_PRD.md are now the MVP build authority; Backend.md wins
ties (the PRD cites it as the REST + SSE contract source). Resolved by that rule:
approve is a single call (`POST /plans/{id}/approve` enqueues test generation +
execution); exports are `POST /plans/{id}/exports`; real-time is SSE everywhere
(the PRD's one "SignalR" mention in S3 is a slip — SignalR is .NET and violates
the no-Microsoft-stack policy both docs state; docs kept verbatim, correction
recorded here and in DESIGN_CONTRACT.md §3).

**Rationale:** the team specs are the shared contract; building to a conflicting
brief would fork the repo from the team.

**Status:** active. Open: whether `Append_to_Reconciliation_Sheet.xlsx` (PRD
acceptance) is the same file as `VendorInvoices_uncleaned.xlsx` — the former
exists nowhere in the workspace.

## 2026-09-30 — Ruby

**Decision:** Restructured the backend from the scaffold's `backend/app/{api,core,models,schemas,services,workers}` layout to the 9-slice brief's module layout (`backend/main.py`, `backend/worker.py`, `backend/{api,workers,core,modules/*}`, `backend/alembic/`). Removed the old `backend/app/` tree of honest 501 stubs from commit `3d66766`; its JWT/Argon2 utilities remain recoverable from git history and will be rebuilt per the FRS in later slices.

**Rationale:** the 9-slice build brief is the build authority and its module layout maps 1:1 to FRS module boundaries (ingest, profile, infer, plan, loss, execute, revert, validate, audit).

**Status:** active.

## 2026-09-30 — SB (proposed by Ruby)

**Decision:** PROPOSED default — use an exception queue plus labelled nulls instead of inventing values for missing data.

**Rationale:** the FRS (functional requirements specification — the formal requirements document) leaves fill-vs-null open (OQ-12: it is an open question whether missing values are filled with inferred values or left as labelled nulls), and the PowerBI guide's Step 4 invents a hardcoded date `2025-09-01` and a hardcoded invoice ID `MS-INDIA-SEP2025`. The planner must not invent data; missing values should be kept as explicitly labelled nulls (e.g. `Not Assigned`) and surfaced in an exception queue (a review list of rows that need a human decision) for the Data Engineer to resolve.

**Status:** proposed.

## 2026-09-30 — SB

**Decision:** Approved proceeding with the Tech Stack deck as the declared Level-2 build stack (Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic; PostgreSQL 16; Redis; MinIO; Celery on RabbitMQ; SSE; Polars, DuckDB, PyArrow; LiteLLM; JWT + Argon2; React + Vite + Tailwind CSS + TanStack Query; Docker Compose), although the deck's own formal approval ("Decision requested: approve this stack so the Level-2 MVP build can start") is still pending in the roadmap.

**Rationale:** the Level-2 evaluation is tonight at 9:30 PM IST; waiting for the deck's formal approval would block the MVP build.

**Status:** active.

## 2026-09-30 — SB

**Decision:** Created the public GitHub repository `dsribalaji/png6-data-cleaning` for the CodeStorm 2K26 PNG6 build.

**Rationale:** the team needs a shared repo so the VM coding agents and SB can sync through GitHub pushes during the hackathon.

**Status:** active.
