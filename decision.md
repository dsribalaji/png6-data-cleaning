# decision.md

Newest first. Each entry: date, decider, decision, rationale, status (active / superseded / proposed).

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
