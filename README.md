# png6-data-cleaning

Agentic Data Cleaning Planner — Team TITAN (NCS26GA-46), CodeStorm 2K26, problem statement PNG6 (track: Generative AI & LLM Applications). Level 2 is a working minimum viable product (MVP — the smallest version that actually works) of the deterministic core flow.

An **agentic data cleaning planner** is software that takes a messy tabular dataset (rows and columns, e.g. from a spreadsheet), automatically studies its quality problems, works out the rules that would clean it, proposes a cleaning plan for a human to review, estimates how much information each step would destroy, then runs the approved plan, checks its own work with generated tests, and can undo everything it did.

The problem statement's story: an invoice-extraction pipeline already reads invoice emails, parses PDFs, and writes one spreadsheet row per invoice — but that output is noisy (mixed date formats, variant supplier spellings, amounts stored as text with `$` signs, line items buried in JSON text cells, missing dates and PO numbers). Today a person cleans that by hand with no record of changes, no undo, and no validation. This planner replaces that manual work with a reversible, test-driven, loss-estimated pipeline.

## Level-2 exit gate

Quoted verbatim from the roadmap deck: "Invoice file goes from upload to validated export without manual steps." Output: 22 invoice rows, 313 line items, gross total 154,292 matched. Rollback restores the original exactly.

**Status: met.** `backend/tests/api/test_exit_gate.py` drives the real app over HTTP (no stubs) on `data/reference/VendorInvoices_uncleaned.xlsx` and checks:

| Check | Result |
|---|---|
| Upload → profile → infer | 22 rows × 14 columns; 7 supplier spellings grouped into 5 suppliers |
| Plan with per-step loss estimate | 5 steps (drop 2 all-null columns, merge supplier names, expand `line_items`, drop redundant `total_price`); total estimated loss 0.6% of cells, under the 5% threshold |
| Approve → generated tests → execute | 8 generated tests pass before and after |
| Reconciliation (recomputed from the source file) | 22 → 22 invoice rows · 313 → 313 line items · gross total (Σ `subtotal_with_vat`) 154,292.47 → 154,292.47 · every line-item amount column matches the JSON it came from |
| Validated export | XLSX with `main` (22 rows) + `LineItems` (313 rows); CSV zip with both tables; pipeline JSON |
| Rollback to v0 | restored snapshot byte-identical (SHA-256) to the original; the raw upload is never modified; export is blocked again until the rolled-back state is validated |
| Audit trail | upload, profile, rules, plan, decisions, approval, execution, validation, export and rollback are all logged |

AI-driven rule inference and plan proposals (via the model layer) are Level 3. Level 2 runs the deterministic core flow only; an LLM key is optional.

## The deterministic core flow

Every dataset runs the same loop, in this exact order: **ingest → profile → infer → plan → approve → execute → verify → rollback**.

- **Ingest** (to take in): upload an XLSX (Excel) or CSV (comma-separated values) file. The original is stored untouched; all work happens on a copy.
- **Profile** (to study): compute data-quality statistics — null counts, distinct values, min/max/mean, nested structures — over the entire dataset.
- **Infer** (to work out meaning): detect groups of values that mean the same thing (e.g. 7 raw supplier-name spellings), arithmetic relationships between columns, candidate keys (columns that uniquely identify a row), and nested child records.
- **Plan**: generate an ordered list of cleaning steps, each with an estimate of the information it would destroy. Steps at or under the loss threshold start as Accept; steps above it wait for a decision.
- **Approve**: a person reviews the plan and accepts, edits, or rejects each step.
- **Execute**: run the approved plan. Every step writes a new version (a Parquet snapshot) and records its inverse operation.
- **Verify**: automatically generated unit tests (small checks of each step) and integration tests (checks across the whole pipeline) run before and after execution, and totals are reconciled against the source. Export is blocked if any test or reconciliation fails.
- **Rollback**: restore any earlier version; rolling back to v0 restores the original snapshot byte-for-byte.

## Run it locally (no Docker)

Prerequisites: Python 3.12, Node.js 20+. Nothing else — SQLite, local file storage and inline jobs are the defaults.

```bash
# Backend (terminal 1)
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python scripts/seed_demo.py
uvicorn planner.main:app --port 8000          # API docs: http://localhost:8000/api/docs

# Frontend (terminal 2)
cd frontend
npm ci
npm run dev                                    # http://localhost:5173
```

Demo logins (local only):

| Role | Email | Password | Can do |
|---|---|---|---|
| Data Engineer | `engineer@example.com` | `Engineer123!` | the cleaning flow: upload, decide, approve, export, roll back |
| Administrator | `admin@example.com` | `Admin123456!` | model settings, users, audit trail |

Walkthrough with the reference file: [docs/LOCAL_SHOWCASE.md](docs/LOCAL_SHOWCASE.md).

## Run it with Docker Compose

```bash
cp .env.example .env
make build && make up          # = docker compose -f deploy/docker-compose.yml build / up -d
```

Frontend http://localhost:5173 · API http://localhost:8000/api/docs. The API container migrates the database and seeds the demo logins on start. By default (`CELERY_TASK_ALWAYS_EAGER=true`) the API runs the job chain inline; set it to `false` with `STORAGE_BACKEND=s3` to hand jobs to the Celery worker over RabbitMQ.

## Tests

```bash
cd backend && pytest -q          # 185 tests, incl. the exit gate above
cd frontend && npm test          # 81 unit tests
# Live browser walk-through against running servers:
cd frontend && BASE=http://localhost:5173 node scripts/live-walkthrough.mjs
```

Note for older CPUs without AVX2: the backend depends on `polars[rtcompat]`, which runs without those instructions.

## Reference dataset

`data/reference/VendorInvoices_uncleaned.xlsx` — one sheet, 34 rows × 19 columns: 22 real invoice rows plus 12 blank padding rows (Excel rows 24–35) and 5 unnamed, fully-empty columns (O–S). Known issue labels used in this repo: `supplier-variants-7-to-5`, `dollar-text-in-json`, `json-buried-line-items`, `float-artifacts`, `invalid-9char-gstin`, `missing-dates-pos`, `padding-rows`, `all-null-columns`, `redundant-total-price`.

## Known limits (Level 2)

- Live job progress (SSE) covers ingest and profile; plan/execute/validate progress is shown from the saved versions and results rather than pushed.
- Missing dates and PO numbers are left as nulls (PROPOSED default P1 in `decision.md`); the planner does not invent values.
- `invalid-9char-gstin` and main-table `float-artifacts` are profiled but not rewritten.
- Upload progress is coarse (0 → 100%).

## Docs

- [AGENTS.md](AGENTS.md) — repo-level instructions for coding agents (stack, layout, conventions).
- [decision.md](decision.md) — decision log, newest first.
- [docs/LOCAL_SHOWCASE.md](docs/LOCAL_SHOWCASE.md) — demo walkthrough.
- [docs/BENCHMARKS.md](docs/BENCHMARKS.md) — Level 2 demo run and timing benchmarks (22 to 30,090 rows).
- [docs/architecture/brief-handoff.md](docs/architecture/brief-handoff.md) — what to build, in what order, what good looks like, what not to build.
