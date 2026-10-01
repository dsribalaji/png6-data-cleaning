# decision.md

Newest first. Each entry: date, decider, decision, rationale, status (active / superseded / proposed).

## 2026-10-01 — Approved UI integrated into the live React frontend (SB approved design, then "integrate to live frontend without breaking anything")

**Decision:** Applied the SB-approved UI design (indigo #4F46E5 system, 220ms Motion
language, light/desktop-first) to the existing frontend without the shadcn CLI. The
existing shadcn-style `src/shared/ui` kit was kept and re-tokened in place — the
approved UI integration contract (2026-10-01, at `~/workspace/verification/DESIGN_CONTRACT_UI_INTEGRATION.md`)
defines the tokens; the older `DESIGN_CONTRACT.md` §10.3 CRMS palette is superseded for
this task by SB's approval.

**How:** three parallel agy workers with disjoint ownership — W1 foundation
(package.json +motion 13.4.6, tailwind tokens, index.css, index.html, shared/ui 17
primitives with Motion-wrapped Modal/Drawer/Toast/DataTable, AppShell), W2 datasets +
diagnosis (8 files), W3 plans + runs + audit (13 files). Imports only from
`motion/react`; reduced-motion honored. Coordinator found one gap the workers missed:
auth pages (Login/AcceptInvite/OIDC) and 403/404 still wore the old orange palette —
restyled to tokens by class-string mapping only, zero logic touched.

**Verified (coordinator re-ran all gates on the final tree):** 88/88 frontend tests
pass, `tsc -b --noEmit` clean, `vite build` green. Slice hygiene confirmed: 48 files,
all under frontend/{index.html,package*,tailwind.config,index.css,src/app/layout,
src/auth/pages,src/pages,src/features/{datasets,plans,runs,audit},src/shared/ui} —
no api.ts/hook/schema/route/RBAC/prop-API changes, no backend changes. Old palette
fully purged from the light theme (dark: variants left dormant, never activated).

**Status:** active. Committed locally only; NOT pushed (SB's standing rule — push needs
his explicit word).

## 2026-10-01 — Real-model e2e verified: Groq openai/gpt-oss-120b returns 11 schema-valid rules (SB's stored key)

**Decision:** Verify the AI inference path against the real model instead of leaving it
fake-only. Replicated `LlmGateway.complete("infer_rules", …)` exactly — same prompt
template (`prompts/infer_rules.v2.md` with the `_RulesOut` JSON schema), same
`_InferRulesPayload` built by `_try_llm_rules` (injection scan + masking, ≤5 samples,
`allow_data_sharing=False`), same `<<<PAYLOAD_JSON` fenced user block — but drove the
model through the groq skill CLI (surrogate auth; the raw key never touched the backend
env, per the skill's rules).

**Result:** the model returned 11 rules on the real reference-workbook profile and every
one validated against the exact `_RulesOut` schema the gateway enforces. Sensible output:
supplier/customer entity groups, `arithmetic(total_price, subtotal_with_vat)`,
`primary_key(invoice_number)`, one-to-many links, semantic types — and notably no
`cross_field_fill` invented, consistent with B7's restraint finding. No hallucin­ated rule
types outside the Literal catalogue.

**Caveat (honest):** this proves model + prompt + schema end-to-end; the one sliver not
exercised is LiteLLM/instructor's own HTTP plumbing, which the B8 stub test covers at the
gateway seam. Verification script at `/tmp/e2e_build_messages.py` (ephemeral).

**Status:** active.

## 2026-10-01 — B7 golden test + B8 cache measurement closed (SB assigned, Ruby coordinated)

**Decision:** Close the two remaining code-level Level-3 gaps with tests only — no engine
changes — via two new files: `backend/tests/unit/test_b7_golden_reference.py` (3 tests) and
`backend/tests/unit/test_b8_cache_measurement.py` (2 tests). Full backend suite now
178/178 (was 173/173).

**B7 — the golden test asserts restraint, not a fill.** Running `infer_rules` on the real
reference workbook fires zero `cross_field_fill` rules, and that is correct: the null
columns (`purchase_order_number`, `supplier_vat_number`) have no genuine sibling holding an
answer — the only constant sibling is `customer_name="HAC"` everywhere, and filling a PO/VAT
number with a customer name would be inventing data, forbidden by OQ-12 and B9's
never-auto-accept rule. The test therefore pins three things: (1) restraint on real data,
(2) a positive control — the synthetic corpus case still fires exactly one rule
(`invoice_date ← batch = "APR-A"`), proving the rule is alive, and (3) `fill_missing` is
never auto-accepted at any confidence. Forcing a fill on the reference file would have
meant fabricating ground truth; that was deliberately not done.

**B8 — the cache is now measured, deterministically.** A counting stub behind the real
`LlmGateway.complete()` seam proves: second identical call makes 0 model calls, and the
cache key (`llm:{sha256(...)}`) changes with prompt version (v1→v2 is a miss). No network,
no litellm import, no API key — CI-safe. No engine seam was needed; `_call_model` was
already monkeypatchable and `complete()` already checks the cache first.

**Rationale:** Both gaps were test-only by evidence, not assumption — the workers tried the
engine path first and the code was already correct. Two workers, disjoint files, agy for
edits (headless needed `--dangerously-skip-permissions` per its own guidance), nothing
committed, reference workbook untouched (SHA-256 unchanged).

**Status:** active. Remaining Level-3 items are branch protection, the lint ratchet, and the
VM-parked deploy items (E5, D-5, D-6, M6). The real-model end-to-end run listed as pending
above was completed the same day: see 2026-10-01 entry "Real-model e2e verified" below.

## 2026-10-01 — Level 3 M3: labelled evaluation benchmark, scorer and CI pass bar (C1, C2, C3)

**Decision:** Replace the three in-code adversarial fixtures with a labelled benchmark
corpus of 18 cases in `backend/src/planner/engine/evaluation/corpus.py`, score them with
`scorer.py`, and enforce the D5 pass bar in CI with the model switched off. `POST /evaluations`
now returns per-case scores alongside the bar; the legacy `adversarial.py` suite is kept as a
sub-result so nothing that depended on it is lost.

**What the corpus found — four real defects, all fixed:**
- **Duplicate header names crashed ingest.** Polars raises `DuplicateError` on a frame with the
  same column name twice. Ingest now disambiguates the later occurrences (`supplier_name`,
  `supplier_name_1`) and warns, instead of dying (FR-044).
- **A UTF-8 BOM was glued to the first column name**, so `﻿invoice_number` broke every
  later reference to that column. CSV is now read as `utf-8-sig` and header names are cleaned.
- **Full-width and zero-width injection text evaded the guard.** `Ｉｇｎｏｒｅ　ａｌｌ…` and
  `Igno<ZWSP>re all…` both passed the literal regex. The scanner now normalises with NFKC and
  strips Unicode format characters before matching, while still displaying the original text
  (FR-045).
- **Latin-1 bytes quarantined the whole file.** Undecodable bytes are no longer a reason to drop
  a row; `errors="replace"` keeps the cell and the row.

**Two labels were wrong, not the engine:** `sparse_column_95` is 95% null, which is sparse rather
than all-null, and `duplicate_rows` has 3 distinct invoice numbers over 5 rows, so it correctly
has no primary key. The ground truth was corrected. A third case exposed a genuine gap: a
near-unique column of code-shaped values was only called an identifier when its *name* contained
"id/number/code", so a `sku` column in the inventory domain was missed. The profiler now also
recognises that shape, which is dataset-agnostic by construction (FR-050).

**Scores with the model off:** 18 cases, 0 crashes, quarantine recall 1.0, quarantine precision 1.0,
injection flag rate 1.0, rule recall 1.0 — above every D5 bar. Backend suite: 231 tests pass.

**Status:** active. M3 remainder: B7 (cross-field fill), B9 (prompt versioning), E3 (API fuzzing).

## 2026-10-01 — Level 3 plan defaults accepted (SB)

**Decision:** SB accepted the PROPOSED defaults in `docs/LEVEL3_PLAN.md` §3:
- D1 (OQ-11) LLM provider at launch: Groq `openai/gpt-oss-120b` via LiteLLM, plus one open-weight fallback on any OpenAI-compatible endpoint.
- D2 (OQ-10) data sent to models: off by default — schema + stats + at most 5 masked samples per column; an Administrator may opt in per model config.
- D3 cloud target: one cloud VM running the same Docker Compose stack, a domain with Let's Encrypt TLS (Kubernetes stays Level 4).
- D4 SSO/MFA: self-hosted Keycloak with required TOTP MFA for all roles.
- D5 evaluation pass bar: 0 crashes; 100% of malformed rows quarantined; at least 95% of injected cells flagged; rule recall at least 0.9 on the labelled sets; LLM-on scores at least LLM-off.
- D6 loss metric: split into *data loss* (rows or values destroyed) and *cells changed*; only data loss is checked against the 5% limit.
- D7 (OQ-05) target date: still OPEN (no default offered).

**Rationale:** Unblocks Level 3 milestone M0; each default follows the tech stack deck, Backend.md or the Level 2 benchmark findings.

**Status:** active.

## 2026-09-30 — Level 2 exit gate met end to end (HTTP + browser); fixes to reach it (Claude, for SB)

**Decision:** Close the gaps between the integrated build and the Level-2 exit gate, and prove it with a no-stub test: `backend/tests/api/test_exit_gate.py` (upload → validated export → rollback over HTTP on the reference file) plus a live browser walk-through (`frontend/scripts/live-walkthrough.mjs`).

**Rationale / what changed:**
- Reconciliation was tautological (it copied the output total into the source total when parsing failed) and the export gate ignored it. It is now recomputed from the source file (`engine/tests_gen/reconcile.py`): row counts, child row counts, per-column sums including line items re-parsed from JSON, and the gross total. The export gate needs every test AND every reconciliation to pass.
- `dollar-text-in-json`: expanded line-item amounts (`"$140.00"`, `"4,735.12"`) are cast to numbers with float artifacts rounded to cents.
- Exports carry every table (XLSX sheets / CSV zip) and a pipeline JSON (FR-037).
- Loss estimates count only destroyed values: dropping an all-null column, a column identical to another, or expanding parseable JSON costs 0%. Steps at or under the threshold default to Accept (PRD S5, FR-031).
- Audit events were silently dropped (no sink was ever bound); they are now persisted for every stage (FR-051).
- Rollback verifies the restored snapshot is byte-identical (SHA-256) and saves the request before dispatching the job.
- Model-config, audit-events and evaluations routers were never mounted; now mounted.
- Frontend could not sign in (it read `user` from the login response), could not upload in Chrome over HTTP/1.1 (streamed upload body), misread profile/validation payloads and sent the wrong rollback field. All fixed; a reload now keeps the session.
- Demo users: `engineer@example.com / Engineer123!` (Data Engineer, runs the flow) and `admin@example.com / Admin123456!` (the old 9-character password could not pass the 12-character login rule).
- Tests: 185 backend (the suite had excluded `src/` slice tests and the stubbed golden test) and 81 frontend pass.

**Status:** active.

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
