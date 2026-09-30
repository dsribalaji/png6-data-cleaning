# Local Showcase Guide

How to demo the PNG6 Agentic Data Cleaning Planner on a laptop, end to end, with the reference invoice file.

## 1. Start it

Either follow "Run it locally" or "Run it with Docker Compose" in the [README](../README.md). No LLM key is needed: Level 2 is deterministic.

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/api/docs · health: http://localhost:8000/api/v1/health/live

## 2. The file

`data/reference/VendorInvoices_uncleaned.xlsx` — what makes it messy:

- 22 invoice rows, plus 12 blank padding rows and 5 empty unnamed columns (dropped at ingest)
- 313 line items packed as JSON text in `line_items`, with amounts like `"$140.00"` and `"4,735.12"`
- 7 supplier spellings for 5 real suppliers (e.g. "Hart Business Solutions, LLC" vs "Hart Business Solutions")
- 2 completely empty columns (`customer_vat_number`, `shipping_addresses`)
- `total_price` duplicates `subtotal_with_vat` on every row

## 3. Walkthrough (about 5 minutes)

1. **Sign in** as the Data Engineer: `engineer@example.com` / `Engineer123!`.
   (The Administrator, `admin@example.com` / `Admin123456!`, manages model settings, users and the audit trail but does not run cleaning, per the PRD role table.)
2. **Upload** — Datasets → Upload dataset → pick the file → Upload & profile. Status goes to **Profiled**: 22 rows × 14 columns.
3. **Profile** — open the dataset: null %, types and flags per column (`all_null`, `nested_json`, …) and the inferred rules (supplier groups 7 → 5, `total_price = subtotal_with_vat`, `line_items` is one-to-many).
4. **Generate plan** — 5 steps, each with its estimated loss:
   1. drop `customer_vat_number` (all null — 0% loss)
   2. drop `shipping_addresses` (all null — 0% loss)
   3. replace values in `supplier_name` (2 cells change spelling — 0.6%)
   4. expand `line_items` into the `LineItems` table (0% loss — every item moves to the child table)
   5. drop `total_price` (identical to `subtotal_with_vat` — 0% loss)

   All are under the 5% threshold, so they start as Accept. Click a row for the rationale and a before/after sample; Edit or Reject any step.
5. **Approve plan** → Confirm. Tests are generated, the plan runs, and the Run page shows every step Done.
6. **Verify** — Tests: Unit 7/7, Integration 1/1. Reconciliation (recomputed from the source file):
   - `row_count` 22 → 22 and `row_count:LineItems` 313 → 313
   - `gross_total:subtotal_with_vat` 154,292.47 → 154,292.47
   - every line-item amount column (amount, charges, tax, total) matches the JSON it came from
7. **Export** — XLSX (sheets `main` 22 rows + `LineItems` 313 rows), CSV (zip, one file per table) or Pipeline (JSON list of the executed steps).
8. **Roll back** — Version timeline → "Roll back here" on v0 → give a reason. A new version (v6) is created whose snapshot is byte-identical (SHA-256) to the original; export is blocked again because that state has not been validated.
9. **Audit** — sign in as the Administrator → Audit trail: every stage above is logged with user and time.

## Troubleshooting

- **Port in use** — `lsof -ti:8000 | xargs kill` (macOS/Linux), or run Vite with `npm run dev -- --port 5174`.
- **Frontend can't reach the API** — Vite proxies `/api` to `VITE_PROXY_TARGET` (default `http://localhost:8000`).
- **"A dataset with this name already exists"** — dataset names are unique; change the name in the upload dialog.
- **Old CPU / "Illegal instruction"** — reinstall the backend so `polars[rtcompat]` is used: `pip install -e ".[dev]"`.

## What the AI does (and doesn't)

Level 2 runs without an LLM. When a model is configured (Model settings, Level 3), it may suggest extra rules and steps — only from the fixed operation catalogue. It never generates or executes code, and a person approves every step.
