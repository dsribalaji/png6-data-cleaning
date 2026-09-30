# png6-data-cleaning

Agentic Data Cleaning Planner — Team TITAN (NCS26GA-46), CodeStorm 2K26, problem statement PNG6 (track: Generative AI & LLM Applications). Tonight's 9:30 PM IST target is the Level-2 evaluation: a working minimum viable product (MVP — the smallest version that actually works) of the deterministic core flow.

## Quick Start (Laptop Demo Mode)

**Prerequisites:** Python 3.12+, Node 24+, a Groq API key (free at console.groq.com)

```bash
# 1. Clone and enter
git clone https://github.com/dsribalaji/png6-data-cleaning.git
cd png6-data-cleaning

# 2. Backend setup
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure (copy and edit)
cp .env.example .env
# Set in .env:
#   DATABASE_URL=sqlite+aiosqlite:///./planner.db
#   GROQ_API_KEY=your_key_here
#   CELERY_TASK_ALWAYS_EAGER=true
#   STORAGE_BACKEND=local

# 4. Run migrations and seed demo user
alembic upgrade head
python scripts/seed_demo.py
# Demo login: admin@example.com / Admin123!

# 5. Start backend (terminal 1)
uvicorn planner.main:app --host 127.0.0.1 --port 8000

# 6. Frontend setup (terminal 2)
cd ../frontend
npm install
npm run dev
# Open http://localhost:5173
```

See [docs/LOCAL_SHOWCASE.md](docs/LOCAL_SHOWCASE.md) for the complete showcase walkthrough with the golden workbook (22 rows, 313 line items, 154,292 total).

An **agentic data cleaning planner** is software that takes a messy tabular dataset (rows and columns, e.g. from a spreadsheet), automatically studies its quality problems, works out the rules that would clean it, proposes a cleaning plan for a human to review, estimates how much information each step would destroy, then runs the approved plan, checks its own work with generated tests, and can undo everything it did.

The problem statement's story: an invoice-extraction pipeline already reads invoice emails, parses PDFs, and writes one spreadsheet row per invoice — but that output is noisy (mixed date formats, variant supplier spellings, amounts stored as text with `$` signs, line items buried in JSON text cells, missing dates and PO numbers). Today a person cleans that by hand with no record of changes, no undo, and no validation. This planner replaces that manual work with a reversible, test-driven, loss-estimated pipeline.

## The deterministic core flow

Every dataset runs the same loop, in this exact order: **ingest → profile → infer → plan → approve → execute → verify → rollback**.

- **Ingest** (to take in): upload an XLSX (Excel) or CSV (comma-separated values) file. The original is stored untouched; all work happens on a copy.
- **Profile** (to study): compute data-quality statistics — null counts, distinct values, min/max/mean, nested structures — over the entire dataset.
- **Infer** (to work out meaning): detect groups of values that mean the same thing (e.g. 7 raw supplier-name spellings), arithmetic relationships between columns, candidate keys (columns that uniquely identify a row), and nested child records.
- **Plan**: generate an ordered list of cleaning steps, each with an estimate of the information it would destroy.
- **Approve**: a person reviews the plan and accepts, edits, or rejects each step.
- **Execute**: run the approved plan. Every step is recorded with its inverse operation, so it can be undone.
- **Verify**: automatically generated unit tests (small checks of each step) and integration tests (checks across the whole pipeline) run before and after execution. Export is blocked if any test fails.
- **Rollback**: restore the output to any earlier version, or the original file byte-for-byte, using the recorded inverse operations.

## Reference dataset

`data/reference/VendorInvoices_uncleaned.xlsx` — one sheet, 34 rows × 19 columns: 22 real invoice rows plus 12 blank padding rows (Excel rows 24–35) and 5 unnamed, fully-empty columns (O–S). Known issue labels used in this repo: `supplier-variants-7-to-5`, `dollar-text-in-json`, `json-buried-line-items`, `float-artifacts`, `invalid-9char-gstin`, `missing-dates-pos`, `padding-rows`, `all-null-columns`, `redundant-total-price`.

## Quickstart

The MVP runs on Docker Compose — a tool that starts every service (API, database, workers, storage, frontend) locally with one command:

```bash
docker compose up
```

Current scaffold state: the compose wiring and app skeletons are in place; the API routers and domain services are functional stubs returning HTTP 501 (`/health` works) — no stub is presented as a working MVP. The command above is the declared entry point per the Tech Stack deck: "Docker Compose runs every service."

## Level-2 exit gate

Quoted verbatim from the roadmap deck: "Invoice file goes from upload to validated export without manual steps." Output: 22 invoice rows, 313 line items, gross total 154,292 matched. Rollback restores the original exactly.

AI-driven rule inference and plan proposals (via the model layer) are Level 3 — Level 2 is the deterministic core flow only.

## Docs

- [AGENTS.md](AGENTS.md) — repo-level instructions for coding agents (stack, layout, conventions).
- [decision.md](decision.md) — decision log, newest first.
- [docs/architecture/brief-handoff.md](docs/architecture/brief-handoff.md) — what to build, in what order, what good looks like, what not to build.
