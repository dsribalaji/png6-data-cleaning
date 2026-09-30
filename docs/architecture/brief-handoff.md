# Brief handoff — png6-data-cleaning

Team TITAN (NCS26GA-46), CodeStorm 2K26, problem statement PNG6 — Agentic Data Cleaning Planner (software that takes a messy tabular dataset, works out cleaning rules, and produces a reversible, test-driven cleaning pipeline with information-loss estimates). Tonight's target is the Level-2 evaluation at 9:30 PM IST: a working MVP (minimum viable product — the smallest version that actually works) of the deterministic core flow.

Brief mode per the architecture-documenter skill: the full interview is deferred past the hackathon. Facts below come from `DESIGN_CONTRACT.md` and the intake files (`~/workspace/png6-intake/requirements.md`, `stack-roadmap.md`, `data-plan.md`); anything not found there is marked UNKNOWN or PROPOSED.

## What to build

The deterministic core flow, in this exact order: **ingest → profile → infer → plan → approve → execute → verify → rollback**.

- **Ingest.** Accept an uploaded XLSX (Excel) or CSV (comma-separated values) dataset. Store an immutable copy of the original; all transforms run on a copy (FRS FR-001, FR-004).
- **Profile.** Compute data-quality statistics over the entire dataset: null counts and percentages, distinct/unique value counts, min/max/mean for numeric and date columns, flags for nested JSON (JSON: JavaScript Object Notation, a text format for structured data) columns, numeric values stored as text with currency symbols, and 100%-null columns (FR-006–FR-012).
- **Infer.** Detect groups of categorical values that likely mean the same thing (e.g. the 7 raw supplier-name spellings that are really 5 suppliers), propose one canonical value (the single approved spelling) per group, infer arithmetic relationships between numeric columns, candidate primary keys (columns that uniquely identify each row), 1:many relationships (one parent invoice row linked to many child line-item rows), and each column's semantic type (date, amount, identifier, name, address, tax number) (FR-013–FR-018).
- **Plan.** Generate an ordered cleaning/transformation plan from fixed operation types (replace value, fill missing, drop column, cast type, derive column, expand nested, deduplicate, standardise format), estimating the information loss (data destroyed by a step) of each step before it runs, plus the cumulative loss of the full plan (FR-021–FR-031).
- **Approve.** The Data Engineer reviews the plan and accepts, edits, or rejects each step; steps whose estimated loss exceeds the configured threshold are held for approval (FR-027, FR-031 — both are Should, not Must; whether approval is required at all is UNKNOWN, FRS OQ-03).
- **Execute.** Run the approved plan on a copy of the data. Record each executed step as a versioned operation with its inverse (FR-032–FR-038).
- **Verify.** Generated unit tests (checks per plan step) and integration tests (schema checks across the pipeline) run before and after execution; row counts and column totals are reconciled against the source; the output is withheld from export if any test fails (FR-039–FR-043).
- **Rollback.** Restore the output to any earlier version via the recorded inverse operations; full rollback reproduces the original dataset byte-for-byte (FR-033/FR-034).

Hard constraints from the intake: originals immutable (FR-004), transforms run on a copy (BR-09), loss estimated before execution (FR-028–FR-031), tests generated and run before/after (FR-039–FR-041), export withheld on test failure (FR-043), quarantine for malformed rows (FR-044), poisoned-cell flagging (FR-045; poisoned data = cell text containing instructions aimed at the LLM), model-agnostic and dataset-agnostic (no single-vendor LLM dependency, no dataset-specific hard-coded rules — FR-048, FR-050).

PROPOSED defaults needing team approval: exception queue + labelled nulls instead of inventing values (the FRS leaves fill-vs-null open as OQ-12; the PowerBI guide's Step 4 invents `2025-09-01` and `MS-INDIA-SEP2025`); Redis (not Valkey); 5% loss limit, 50 MB upload, one role per user.

## In what order

The deck's first-slice build order (slide 7): 1. Approve the stack → 2. Confirm the defaults → 3. Set up the repository → 4. Build the first slice: "Upload → profile → live progress on screen, tested on the invoice reference file."

The reference file is `data/reference/VendorInvoices_uncleaned.xlsx` — one sheet, 34 rows × 19 columns: 22 real invoice rows, 12 blank padding rows (Excel rows 24–35), 5 unnamed fully-empty columns (O–S). Observed issue labels: `supplier-variants-7-to-5`, `dollar-text-in-json`, `json-buried-line-items`, `float-artifacts`, `invalid-9char-gstin`, `missing-dates-pos`, `padding-rows`, `all-null-columns`, `redundant-total-price`.

The roadmap's Level-2 build phase, in order: Requirements ("Lock the Must-have FR rows; confirm defaults: approver (OQ-03), 5% loss limit, 50 MB upload, one role per user") → Design (database schemas per module, job event contracts, OpenAPI spec — a machine-readable API description, screens from the wireframes) → Build (schemas and migrations; core logic for ingest, profile, plan, loss estimate, execute, rollback; REST APIs; React screens) → Test ("Unit and integration tests; undo checked for every cleaning step; golden test on the invoice file") → Release ("Runs on Docker Compose; demo to AP and Data Engineering").

## What good looks like

The Level-2 exit gate, quoted verbatim from the roadmap deck: "Invoice file goes from upload to validated export without manual steps." Output: 22 invoice rows, 313 line items, gross total 154,292 matched. Rollback restores the original exactly.

The nine screens from the wireframe bundle: Datasets + upload popup, Profile report, Plan review, Execute + rollback, Generated tests, Quarantine banner, Audit trail, Model settings, Dataset detail.

## What not to build

Out of scope for Level 2 (from the contract §7 and the roadmap): SAP posting (draft invoice creation, posting, payment execution), PO flip / 2-way or 3-way matching, dashboards and report visualisation (Power BI Guide Steps 10–15), changes to the upstream n8n extraction workflow (email ingestion, PDF download, LlamaParse parsing, LLM extraction — "The extraction pipeline was the quick win. Our PNG6 work starts where it ends."), Keycloak / OpenBao (later: SSO/MFA and secret storage), Kubernetes (Level 4), and AI rule inference via LiteLLM (Level 3).

Also marked Won't in the FRS for this release: FR-053 (no dashboards or visualisations), FR-054 (no modification of the upstream n8n workflow).

## UNKNOWNs that affect the build

- OQ-03: is human approval required before a plan executes, or may low-risk steps run automatically? (FR-027/FR-031 are Should.)
- OQ-04: what information-loss threshold holds a step for approval? (PROPOSED default: 5% loss limit.)
- OQ-09: max dataset size / processing time? (PROPOSED default: 50 MB upload.)
- OQ-12: fill missing values with inferred values, or leave labelled nulls? (PROPOSED default: exception queue + labelled nulls — see `../../decision.md`.)
- Whether tonight's 9:30 PM IST evaluation wants a live demo or a recording, and how it is scored (not stated in either deck).
