# Level 3 Plan — Intelligence, Security & Deployment

Status: **ACTIVE** — defaults D1–D6 accepted by SB on 2026-10-01 (see `decision.md`); D7 open · 2026-10-01 · baseline commit `a47a13a`

Sources: the Delivery Roadmap deck (slide 4), the PNG6 problem statement, FRS v0.1 (FR-013–FR-020, FR-044–FR-052, NFR-01–NFR-09, OQ-10/11), `files/Backend.md`, the Tech Stack deck, `DESIGN_CONTRACT.md` §10, `docs/architecture/brief-handoff.md`, [BENCHMARKS.md](BENCHMARKS.md), and an audit of the current code.

## 1. Exit gate (verbatim, roadmap slide 4)

> Users sign in with SSO and MFA; roles enforced on every API
> Evaluation benchmark passes; bad input is quarantined, never crashes a job
> Every release goes through the pipeline with no manual deploys

The roadmap also says that Level 3 "makes the MVP secure, intelligent and publicly deployed":

- **Build:** AI rule inference and plan proposals via LiteLLM; prompt-injection guard; evaluation harness; TLS and encryption at rest.
- **Test:** adversarial benchmark set; security scans (code, dependencies, containers); API fuzzing.
- **Release:** an automated pipeline deploys to cloud infrastructure behind HTTPS.

## 2. Where we start (code audit, 2026-10-01)

| Area | State | Evidence |
|---|---|---|
| LLM gateway (LiteLLM + instructor, cache, redaction) | **Built, never exercised** | `llm/gateway.py`; `infer_rules` / `propose_steps` are wired in `profiling/tasks.py` and `planning/tasks.py`. No API key and no `model_configs` row exist, and 0 inferred rules have `prompt_version` set, so every rule so far came from the deterministic code. |
| LLM failure handling | **Silent** | Both call sites use `except Exception: return []`. A broken key or bad output is invisible to the user and the audit trail. |
| LLM step validation | **Partial** | Proposed steps are checked only for an operation name in the catalogue. Their parameters are not run through `op.validate()` before they enter the plan. |
| Dataset-agnostic rule (FR-050) | **Violated** | `engine/ingest/reader.py:162` and `:196` switch off the quarantine rule for files named `vendorinvoices*` or with invoice headers. `planning/tasks.py:172` falls back to `invoice_number` as the key, and `:283` defaults the child table name to `LineItems`. |
| Prompt-injection guard (FR-045) | Basic | `engine/guards/scanner.py` matches regex patterns. Flagged cells are dropped from LLM samples but are not shown to the user. |
| Quarantine (FR-044) | Basic | Ingest quarantines rows whose first cell is empty. There is no parse-failure, wrong-width or type-failure quarantine. |
| Evaluation harness (FR-047) | Thin | `evaluation/adversarial.py` has 3 synthetic workbooks and only scores "quarantined, not crashed". There is no ground truth for inference quality and no pass bar. |
| Roles on every API | **Done** | Commit `fdfc3b4` + `tests/api/test_auth_required.py`. |
| SSO / MFA | Not started | JWT + Argon2 only. The `TokenVerifier` seam exists in `core/security.py` (per Backend.md). |
| Secrets | MVP | Fernet for model keys. The JWT key is below 32 bytes. No OpenBao. |
| TLS / encryption at rest | Not started | Plain HTTP; volumes unencrypted. |
| CI/CD | Not started | No `.github/`, no pipeline, no image registry, no cloud host. |
| Security scans / API fuzzing | Not started | — |

## 3. Decisions needed before building

| # | Decision | Why it blocks | Default (ACCEPTED 2026-10-01 unless noted) |
|---|---|---|---|
| D1 | **OQ-11:** LLM provider(s) at launch | Needed for keys, cost and data terms | Groq `openai/gpt-oss-120b` (already verified in contract §10.3), plus one open-weight fallback via any OpenAI-compatible endpoint |
| D2 | **OQ-10:** what data may go to the model (GDPR) | Controls `allow_data_sharing` and masking | Default off: schema + stats + ≤5 masked samples per column; the Administrator can opt in per config |
| D3 | Cloud target and budget | Deploy pipeline and TLS depend on it | One cloud VM running the same Docker Compose stack (Kubernetes is Level 4), a domain with Let's Encrypt TLS |
| D4 | SSO/MFA: self-hosted Keycloak (deck) or a hosted identity provider | Keycloak + OpenBao need about 1.5 GB RAM more; the dev laptop has 7.6 GB | Keycloak as the deck says, with TOTP MFA required for all roles |
| D5 | Evaluation pass bar | "Evaluation benchmark passes" needs a number | 0 crashes; 100% of malformed rows quarantined; ≥95% of injected cells flagged; rule recall ≥0.9 on the labelled sets; LLM-on ≥ LLM-off |
| D6 | Loss metric: should lossless casts count? (from BENCHMARKS §4) | AI will propose more steps; the threshold logic must mean something | Split into *data loss* (rows or values destroyed) and *cells changed*; only data loss is checked against the 5% limit |
| D7 | Target date (OQ-05) | Scheduling | — (the plan below is ordered, not dated) |

## 4. Workstreams

Each item states what "done" looks like. Size: S ≤ ½ day · M ≈ 1–2 days · L ≈ 3+ days.

### A. Honest baseline (first; small but it blocks the evaluation)

| # | Task | Done when | Size |
|---|---|---|---|
| A1 | Remove the reference-file special case in ingest (`reader.py:162`/`:196`). Replace the "first cell empty" rule with generic malformed-row rules: wrong column count, unparseable in a typed column, control characters or encoding errors. | The golden test passes with the file renamed and no name or header checks anywhere in `engine/`. | M |
| A2 | Remove the `invoice_number` / `LineItems` fallbacks in `planning/tasks.py`. Use the inferred primary key; if there is none, skip the step and say so in its rationale. The child table is named from the source column. | `grep -ri invoice engine modules` finds nothing outside tests and fixtures. | S |
| A3 | Add a CI guard test that fails if the engine code mentions dataset-specific names (FR-050). | The test is in the suite. | S |
| A4 | Find out why profiling a 22-row file takes about 23 s (BENCHMARKS §4); check whether the LLM attempt is timing out. | The cause is documented, and fixed if cheap. | S |

### B. Intelligence — AI rule inference and plan proposals (FR-013–FR-019, FR-046, FR-048)

| # | Task | Done when | Size |
|---|---|---|---|
| B1 | Configure a provider through Model settings (D1) and **wire it into the tasks**: found in M0 that `infer_rules`/`propose_steps` read only env vars (`_default_env_resolver`); `model_config.public.resolve_llm_config()` has no caller, so the admin's saved model is ignored. Also skip importing LiteLLM when no model is configured. | `model_configs` has an active row; `POST /model-config/test` returns OK; a profile run uses the saved model (audit shows provider/model). | M |
| B2 | Make LLM failures visible. A failure becomes a job *warning* (not a failure), an `llm.failed` audit event, and a banner in the UI ("AI suggestions unavailable — deterministic rules used"). | Failures (bad key, timeout, invalid output) are shown and audited; the pipeline still completes. | M |
| B3 | Merge rules from both sources. De-duplicate LLM and deterministic rules; keep the source (`llm` / `heuristic`) and `prompt_version` on every rule. | The Profile screen shows a source badge per rule; the rules table records `prompt_version`. | M |
| B4 | Validate every LLM-proposed step through `op.validate(params, schema)` and a dry-run `estimate_loss` before it enters the plan. Reject invalid steps and log why. | A fuzz test with random proposed JSON never produces a plan step that fails at execute. | M |
| B5 | Plan review UX: an "AI-suggested" tag, rationale, confidence, and the evidence rows. Low-confidence steps (< 0.6) start as *Review*, never *Accept*. | The UI shows this; a Playwright spec covers it. | M |
| B6 | Sparse datasets (FR-046): report plan confidence overall and per step when columns are ≥95% null. | The sparse benchmark shows the confidence in the API and the UI. | S |
| B7 | Cross-field fill (FR-019, Should), e.g. a missing invoice date found inside the line items. It is always proposed, never auto-accepted (OQ-12: labelled nulls by default). | A rule type and step exist; there is a golden test on the reference file. | M |
| B8 | Check the cache: Redis `llm:{sha256}`, 7-day TTL, hits and misses shown in metrics. | A second run of the same dataset makes 0 model calls. | S |
| B9 | Prompt versioning: `infer_rules.v2` and `propose_steps.v2` prompts with few-shot examples taken from the benchmark (not from the reference file). | Evaluation scores are recorded per prompt version. | M |

### C. Adversarial resilience and the evaluation harness (FR-044–FR-047, NFR-07)

| # | Task | Done when | Size |
|---|---|---|---|
| C1 | A labelled benchmark set in `backend/tests/fixtures/benchmarks/`. Each dataset has an `expected.json` (rules, quarantined rows, flagged cells). Cases: malformed and ragged rows; injected instructions (including hidden text and unicode tricks); 95%-sparse columns; mixed types; duplicate or blank headers; an empty file; a 50 MB boundary file; wrong encoding; CSV formula injection (`=HYPERLINK(...)`, `+cmd`); huge cells; non-invoice domains (for example HR and inventory) to prove FR-050. | ≥ 12 labelled datasets checked in. | L |
| C2 | Scorer: crashes, quarantine precision/recall, injection flag rate, rule precision/recall, step validity, loss-estimate error against actual. Runs with the LLM off and on. | `POST /evaluations` returns these scores; the Evaluation screen shows them per run. | M |
| C3 | Pass bar (D5) enforced in CI with the LLM **off** (deterministic, free). An LLM-on run happens nightly or on demand. | CI fails when a score drops below the bar. | S |
| C4 | Show poisoned cells in the UI: flagged cells are listed on the Profile screen with the reason, and are excluded from model samples. | The UI shows them; an audit event records them. | S |
| C5 | Escape spreadsheet formulas on export: cells starting with `= + - @` get a leading `'` in XLSX and CSV. | A benchmark case proves it. | S |

### D. Security (NFR-01–NFR-03)

| # | Task | Done when | Size |
|---|---|---|---|
| D-1 | Threat model (STRIDE — a checklist of spoofing, tampering, repudiation, information disclosure, denial of service and elevation of privilege) for the upload, LLM and export paths, in `docs/architecture/threat-model.md`. | Reviewed; each threat maps to a control or an accepted risk. | M |
| D-2 | Keycloak (OIDC) SSO with required TOTP MFA. Realm roles map to `data_engineer / administrator / auditor / viewer`. Add `KeycloakTokenVerifier` behind the existing seam; keep local JWT only in dev mode. The frontend uses the OIDC PKCE flow. | Sign-in goes through Keycloak with MFA; the role changes the UI and the API. | L |
| D-3 | A route-coverage test: every registered route except an explicit allowlist (health, auth, docs) has an auth dependency. It builds on `test_auth_required.py`. | Adding an unprotected route fails CI. | S |
| D-4 | OpenBao for the JWT/OIDC client secret, the Fernet key, DB and MinIO credentials, and LLM keys. The app reads them at startup; `.env` only points to OpenBao. | No secret sits in `.env` on the server. | M |
| D-5 | TLS: Caddy or Traefik as a reverse proxy with automatic Let's Encrypt, HSTS and security headers. Postgres, Redis, RabbitMQ and MinIO ports are not exposed publicly. | An SSL Labs grade of A; only 443 (and 80, which redirects) is open. | S |
| D-6 | Encryption at rest: an encrypted cloud disk for all volumes, MinIO server-side encryption, and the Postgres volume on the encrypted disk. | Documented and checked on the host. | S |
| D-7 | Rate limiting (slowapi, Redis-backed) on login and upload; the lockout (5 failures / 15 min) is verified. | Tests cover it. | S |
| D-8 | Level 2 carry-overs: a JWT key ≥ 32 bytes, and the refresh endpoint's `X-Requested-With` check verified. | Done. | S |

### E. CI/CD and cloud deployment (NFR-09)

| # | Task | Done when | Size |
|---|---|---|---|
| E1 | GitHub Actions on every PR: ruff, backend pytest (Postgres service), frontend Vitest + build, the exit-gate test, the benchmark scorer (LLM off), and the Playwright walkthrough against a Compose stack. | Required checks block merge to `main`. | M |
| E2 | Security scans in CI: `bandit` or `semgrep` (code), `pip-audit` + `npm audit` (dependencies), `trivy` (container image), `gitleaks` (secrets). | High or critical findings fail the build, unless an accepted risk is recorded. | S |
| E3 | API fuzzing: `schemathesis` against `/api/docs/openapi.json` with an authenticated token, run against the Compose stack. | No 5xx responses; results are uploaded as a CI artifact. | M |
| E4 | Build one image per commit and push it to GHCR (GitHub's container registry), tagged with the git SHA. | The image is pulled by digest when deploying. | S |
| E5 | Deploy job: on a merge to `main`, a protected environment SSHes into the cloud VM (D3), runs `docker compose pull && up -d`, runs migrations, then a smoke test (health + login + the exit gate on the reference file). If the smoke test fails, it rolls back to the previous tag automatically. | Every release goes through this; manual `ssh` deploys are not used (no one has a shell on the host except the pipeline, or access is audited). | M |
| E6 | Public demo: the HTTPS URL, seeded demo users in Keycloak, and a runbook in `docs/DEPLOYMENT.md`. | Someone outside the team can sign in and run the demo. | S |

## 4a. M0 progress (2026-10-01)

- **A1 done.** The file-name/header special case is gone. Ingest now quarantines only rows with data beyond the header or undecodable text; a missing value stays as a null. Every quarantined row is saved (`quarantine/<id>.parquet` + a `quarantine_records` row with its reason). Before this fix, any dataset with a blank first cell lost those rows silently: 930 rows (3.1%) of the large CSV once it is renamed.
- **A2 done.** The key column for nested expansion is chosen from the profile (the identifier column with the most distinct values); the child table is named from the source column.
- **A3 done.** `tests/unit/test_dataset_agnostic.py` fails if pipeline code mentions reference-dataset names.
- **A4 done.** Root cause: the Docker image had no compiled bytecode (`uv pip install` without `--compile-bytecode` plus `PYTHONDONTWRITEBYTECODE=1`), so each process recompiled LiteLLM and the other libraries on import. Fixed in `backend/Dockerfile`: the reference file now takes 13 s end to end instead of 33 s, and profiling 4.4 s instead of 22.6 s.
- Also fixed on the way: concurrent uploads with the same name returned a raw 500 (now 409 `DATASET_NAME_TAKEN`); the n8n folder poll never started ingest (an undefined name was swallowed by `except`).

## 4b. M1 progress (2026-10-01)

- **E1 / E2 / E4 written:** `.github/workflows/ci.yml` has five jobs.
  - backend: correctness lint + pytest
  - frontend: Vitest + strict build
  - security: gitleaks, bandit, pip-audit, npm audit
  - e2e: the Compose stack + the HTTP benchmark on the reference file + the browser walk-through
  - image: build, trivy scan, then push to GHCR from `main`

  Local calibration: bandit has 0 medium or high findings; pip-audit has 0 known vulnerabilities; npm audit has 0 high (3 moderate, dev only). Gitleaks and trivy have not been run locally; their first CI run will show any findings.
- **Not yet:** CI has not run (it needs the push). After the first green run, make the four checks required on `main` (GitHub branch protection; a repository setting, not code).
- **D-3 done:** `tests/api/test_route_auth_coverage.py` walks all 43 routes; any route without an auth dependency that is not on the public allowlist fails the build.
- **D-8 done:** the app refuses to start with a JWT key under 32 bytes or with the `.env.example` placeholder (`tests/unit/test_config_jwt_secret.py`); the local `.env` key was rotated. The refresh endpoint's `X-Requested-With` check was confirmed in code and in the frontend.
- Lint debt is too large to gate fully today: 97 B008, 54 blind-except and others (about 300 findings; 57 files not ruff-formatted). CI gates only on undefined names and syntax errors. Ratchet the rest per file.
- Also fixed: an undefined name in `model_config` (a dead fallback class), and a circular import that made `test_w3_model_config.py` fail when run on its own.

## 5. Order

Each milestone ends with a tested, working state. The pipeline goes first so that everything after it ships through CI.

1. **M0 — Decisions and honest baseline:** D1–D7 answered or defaults accepted; A1–A4.
2. **M1 — Pipeline first:** E1, E2, E4, D-3, D-8.
3. **M2 — Intelligence:** B1–B6, B8, C4, C5.
4. **M3 — Evaluation:** C1–C3, B9, B7, E3.
5. **M4 — Security:** D-1, D-2, D-4, D-7.
6. **M5 — Deploy:** D-5, D-6, E5, E6.
7. **M6 — Exit-gate run:** a documented run like [BENCHMARKS.md](BENCHMARKS.md), against the public URL.

## 6. Exit-gate evidence

| Gate line | Evidence |
|---|---|
| Users sign in with SSO and MFA | A Playwright spec against the public URL: Keycloak login + TOTP; a screenshot in the exit-gate report |
| Roles enforced on every API | The route-coverage test (D-3) + `test_auth_required.py` + a role-matrix test (each role × each route) |
| Evaluation benchmark passes | The scorer output over the labelled set meets the pass bar (D5); LLM-off in CI plus one recorded LLM-on run |
| Bad input is quarantined, never crashes a job | The benchmark crash count is 0; the quarantine precision and recall |
| Every release goes through the pipeline, no manual deploys | GitHub Actions history: each deployed SHA has a green pipeline run; the deploy log on the host |
| HTTPS, TLS, encryption at rest (roadmap build line) | The SSL Labs report; host disk-encryption check |

## 7. Out of scope (Level 4 or later)

Kubernetes, Helm or KEDA autoscaling; Postgres read replicas; full Loki, Tempo and alert routing (NFR-08); k6 load tests; dashboards (FR-053); n8n changes (FR-054); SAP posting. XLSX export speed (BENCHMARKS §4) is done only if it is cheap; otherwise it goes to Level 4.

## 8. Risks

| Risk | Mitigation |
|---|---|
| The dev laptop (i3, 7.6 GB) can't run the full stack plus Keycloak plus OpenBao | Use the cloud VM as staging; keep local dev on the JWT verifier |
| LLM output is unstable or costly; free-tier rate limits | Cache (B8); run the LLM-off evaluation in CI; LLM-on runs are scheduled and budgeted |
| AI suggestions lower quality (hallucinated columns or bad parameters) | B4 validation + dry-run; the LLM can only choose from the fixed catalogue; a human approves every step |
| GDPR exposure from samples | D2 default off; masking + injection guard; audit every model call (without payload values) |
| Removing the reference-file special case (A1) breaks the golden test | Expected. That test was passing for the wrong reason; fix the generic rules until it passes honestly |
| Keycloak integration cost is high | D4 lets the team choose a hosted identity provider behind the same verifier seam |
