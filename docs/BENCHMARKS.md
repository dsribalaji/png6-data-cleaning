# Level 2 Benchmarks and Demo Run — 2026-10-01

This page records a full demo run and timing benchmark of the Level 2 planner, taken on 2026-10-01 against the Docker Compose stack (`make build && make up`). It is the baseline to compare against once Level 3 (AI rule inference) lands.

## 1. Setup

| Item | Value |
|---|---|
| Machine | Intel Core i3 M 370 @ 2.40 GHz, 4 threads, 7.6 GiB RAM (an old laptop — a realistic worst case) |
| Stack | Docker 26.1.5, `deploy/docker-compose.yml`, all 10 services up |
| Job mode | `CELERY_TASK_ALWAYS_EAGER=true` — the API runs each job chain itself (the "inline" Level-2 demo mode), so the worker container stays idle |
| Storage | local volume (`STORAGE_BACKEND=local`) |
| Code | commit `40d6faa` |
| Loss limit | 5% per step (PROPOSED default) |

## 2. Automated checks

| Suite | Result | Time |
|---|---|---|
| Backend `pytest -q` (includes the HTTP exit gate) | **185 passed** | 40.7 s |
| Frontend `npm test` (Vitest) | **81 passed** (8 files) | 38.1 s |
| Frontend `npm run build` | OK | 28.7 s |

## 3. Pipeline benchmark

**How it was measured.** `backend/scripts/benchmark.py` drives the real HTTP API, just like the browser does, and times each stage: upload → profiled → plan generated → approve (tests generated, plan executed, validation run) → XLSX export → CSV export. Every plan step is accepted. The inputs are the reference file plus the first 1,000 and 10,000 rows of the large messy CSV, and then the whole CSV (`files/VendorInvoices_LARGE_messy.csv`, kept out of git).

Reproduce (with the stack running):

```bash
backend/.venv/bin/python backend/scripts/benchmark.py \
  data/reference/VendorInvoices_uncleaned.xlsx  <more files...>  --json out.json
```

### Results (seconds)

| File | Rows in → out | Upload | Profile | Plan | Execute + validate | Export XLSX | Export CSV | **Total** |
|---|---|---|---|---|---|---|---|---|
| Reference `.xlsx` (18 KB) | 22 → 22 | 2.5 | 22.6 | 1.5 | 3.4 | 1.0 | 0.5 | **33.0** |
| CSV, 1k (0.6 MB) | 995 | 2.2 | 31.2 | 2.8 | 3.1 | 1.9 | 0.4 | **51.0** |
| CSV, 10k (6.2 MB) | 9,936 | 1.2 | 50.9 | 3.9 | 10.6 | 28.4 | 0.8 | **100.6** |
| CSV, full (18.7 MB) | 30,090 | 1.9 | 98.0 | 6.4 | 19.9 | 63.8 | 1.8 | **195.9** |

"Rows" is the count after ingest, which drops blank padding rows (so 30,290 raw rows become 30,090).

### Quality results

| File | Plan steps | Generated tests | Reconciliation checks | Validation | Rows removed by the plan | Export size (XLSX / CSV zip) |
|---|---|---|---|---|---|---|
| Reference | 5 | 8/8 passed | 10/10 matched | **passed** | 0 | 17.7 KB / 6.9 KB |
| 1k | 12 | 14/14 | 8/8 | **passed** | exact duplicates only | 235 KB / 115 KB |
| 10k | 13 | 14/14 | 8/8 | **passed** | exact duplicates only | 2.4 MB / 1.2 MB |
| Full | 13 | 14/14 | 8/8 | **passed** | 90 exact duplicates (0.3%) | 7.1 MB / 3.5 MB |

*Reconciliation* means recomputing row counts and money totals from the original file and checking that the cleaned output still matches them.

### Resource use (sampled every 5 s by `docker stats`)

| Container | Peak CPU | Peak memory |
|---|---|---|
| api (runs the jobs inline) | 124% (≈1.2 cores) | 818 MiB |
| postgres | 61% | 41 MiB |
| worker (idle in inline mode) | 1% | 348 MiB |

## 4. What the numbers say

- **All four sizes pass the full loop.** Every run reached a validated export, and every generated test and reconciliation check passed.
- **Profiling is the slowest step.** It takes 50% of the total time on the full file, and about 23 s even for 22 rows, so most of that is fixed startup cost rather than per-row work.
- **XLSX export grows faster than the file does.** It took 28 s at 10k rows and 64 s at 30k, while CSV export stays under 2 s. openpyxl writes the workbook one cell at a time. The fix is a streaming (write-only) writer, but only if Excel output at this size matters.
- **Upload returns in about 2 s at every size**, because ingest and profiling run in the background.
- **"Estimated loss" measures changed cells, not lost data.** On the messy CSV the plan total is 28.7%, but only 0.3% of rows are removed (90 exact duplicates). The rest comes from:
  - four `cast_type` steps that turn currency text like `"$1,234.50"` into numbers, 5.6% of cells each
  - value standardisation steps such as supplier and address spelling, date format and priority flag, 0.7–3.7% each

  The four cast steps are each **above the 5% per-step limit**, so a person has to accept them explicitly (the benchmark accepted every step). **Team decision needed:** should a lossless type cast count toward the loss limit?

## 5. Browser demo run

`frontend/scripts/live-walkthrough.mjs` (Playwright driving Chrome) ran the reference file through the real UI on the Docker stack at http://localhost:5173. It covered: sign in as engineer, upload, profile, generate plan, accept all steps, approve, run, export XLSX/CSV/Pipeline, roll back to v0, reload, and finish on the dataset list. Screenshots are in [`benchmarks/demo-2026-10-01/`](benchmarks/demo-2026-10-01/), and the raw benchmark JSON is in [`benchmarks/2026-10-01-docker.json`](benchmarks/2026-10-01-docker.json).

- Result: every step completed, all 5 plan steps show **Done**, and the tests show Unit 7/7 and Integration 1/1. All three exports downloaded.
- The only API error was one `POST /auth/refresh → 401` on first page load. The app tries to restore a session before anyone has signed in, so there is no cookie yet; this is expected.

## 6. Issues found during this run

| # | Severity | Issue |
|---|---|---|
| 1 | ~~High — security~~ **Fixed** | Ten endpoints used a placeholder that did no authentication (get/create plan, decide step, approve, get profile, get rules, export, rollback, list versions, get validation), and `GET /api/v1/files/{key}` was open. Now: read endpoints need any signed-in role; create plan, decide step, approve and rollback need Data Engineer or Administrator; export also allows Viewer; file downloads need any signed-in user. Export and rollback now record the real user in the audit trail. Covered by `tests/api/test_auth_required.py`; verified live (401 without a token) and via the browser walkthrough. |
| 2 | Medium | The JWT signing key in `.env` is shorter than the recommended 32 bytes. |
| 3 | Low — UI | After the run finishes, the Run page still shows the "Profiled" badge, the header says "Job profile succeeded", and the live-update indicator says "Reconnecting…". |
| 4 | Low — performance | XLSX export is slow above about 10k rows (see §4). |
| 5 | Decision | Whether type casts count as "loss" (see §4). |
