# Agentic Data Cleaning Planner — Frontend PRD (MVP)

| Field | Value |
|---|---|
| Product | Agentic Data Cleaning Planner (PNG6), web client |
| Version | 0.1 (Draft), 30 Sep 2026 |
| Sources | FRS v0.1 · Wireframes 1a–1l · Backend CLAUDE.md (FastAPI REST + SSE contract) · CRMS UI agent CLAUDE.MD (theme rules) |
| Owner | OPEN (OQ-02) |

---

## 1. Purpose

Give Data Engineers one screen flow to upload an extracted dataset, see what is wrong with it, review an AI-proposed cleaning plan with the data loss estimated, run it with generated tests, and roll back if needed. Give Administrators model and user settings, and give Auditors a read-only audit trail. This replaces the 9-step manual Power Query process (FRS §2.3).

## 2. Users and Roles

| Role | Lands on after login | Can do (wireframe 1c) |
|---|---|---|
| Data Engineer | `/datasets` | Upload, view profile, decide plan steps, approve, execute, roll back, export, run evaluation |
| Administrator | `/settings/model` | Model settings, users & roles, view audit trail, run evaluation |
| Auditor | `/audit` | View profiles/plans read-only, view + export audit trail |
| Viewer (AP Clerk / Supervisor, OQ-20) | `/datasets` | Read-only views, export validated tables |

**RBAC rule:** nav items, routes and buttons the role cannot use are **hidden, not disabled**. Opening a forbidden URL directly shows the 403 page with the text "You don't have access to this page." The backend enforces the same policies, so the UI check is only for usability.

## 3. MVP Scope

### In
| # | Screen | Route | Wireframe | FR |
|---|---|---|---|---|
| S1 | Login | `/login` | 1a (email + password; MFA step hidden until OQ-17) | NFR-03 |
| S2 | Accept invite / set password | `/invite/:token` | — (new) | OQ-21 |
| S3 | Datasets list + upload modal | `/datasets` | 1d | FR-001 – FR-005 |
| S4 | Dataset profile + inferred rules + quarantine | `/datasets/:id` | 1e | FR-006 – FR-020, FR-044 |
| S5 | Plan review | `/plans/:id` | **1f table + 1g diff drawer on row click** | FR-021 – FR-031 |
| S6 | Run, tests, versions, rollback | `/plans/:id/run` | 1i | FR-032 – FR-043 |
| S7 | Model settings | `/settings/model` | 1j | FR-048 – FR-049 |
| S8 | Users & roles | `/settings/users` | 1k | OQ-21 |
| S9 | Audit trail | `/audit` | 1l | FR-051 – FR-052 |
| S10 | Evaluation runs (list + start) | `/evaluation` | — (simple table) | FR-047 |
| — | 403, 404, session-expired pages | — | — | — |

### Out (MVP)
SSO login (1b, OQ-19), MFA (OQ-17), dashboards/visualisation (FR-053), multi-role switching (OQ-21), mobile layouts below 1024px (desktop-first admin tool).

---

## 4. Tech Stack

| Concern | Choice | Reason |
|---|---|---|
| Framework | **React 19 + TypeScript 5 (strict)** | Required by the CRMS UI agent |
| Build | **Vite 6** | Fast dev server, simple static build for nginx container |
| Styling | **Tailwind CSS 3.4** + CRMS theme tokens | Mandatory per CRMS CLAUDE.MD (Nunito Sans, `#fd6321` primary, `dark:` variants) |
| Routing | **React Router 7** (data routers, route `loader` guards) | Role-based route guards |
| Server state | **TanStack Query 5** | Caching, retries, invalidation after real-time events |
| Real-time | **Server-Sent Events** via `fetch` + **eventsource-parser** (so the Bearer header can be sent) | Job progress from `GET /datasets/{id}/events`, so no polling |
| Forms | **React Hook Form + Zod** | Field rules from the wireframe annotations as Zod schemas |
| Tables | **TanStack Table 8** | Sorting, paging, row selection for datasets, profile, steps, audit |
| Client state | **Zustand** (auth session, UI prefs only) | Small; server data stays in TanStack Query |
| HTTP | **ky** with an auth/refresh interceptor | Single place for 401 → refresh → retry |
| API types | **openapi-typescript** generated from FastAPI `/api/docs/openapi.json` | Types stay in sync with the API |
| Icons / charts | **@tabler/icons-react**, **react-apexcharts** | Required by the CRMS UI agent |
| Dates | **date-fns** | Formats `dd-MM-yyyy` / `dd-MM-yyyy HH:mm` (OQ-22) |
| Testing | **Vitest + Testing Library**, **MSW** (API mocks), **Playwright** (E2E) | |
| Quality | ESLint (typescript-eslint, jsx-a11y), Prettier, Husky pre-commit | |

## 5. Architecture Style

- **Feature-sliced SPA:** each feature folder owns its routes, API hooks, components and Zod schemas. Shared UI primitives follow the CRMS patterns only.
- **Server state is the source of truth.** Components read through TanStack Query hooks. SSE events only **invalidate or patch** query caches; they don't hold their own state.
- **API layer is thin and typed:** `api/client.ts` (ky instance) plus generated `api/schema.d.ts`. Each feature has `api.ts` exporting query/mutation hooks.
- **Auth:** the access token is kept in memory (Zustand, not localStorage). The refresh token is an httpOnly cookie set by the API. On a 401 the client calls `/auth/refresh` once, then retries; if that fails it redirects to `/login?expired=1`.
- **Permissions:** `usePermission('plan.approve')` reads the role from `/auth/me`. `<Can perm="…">` wraps any action. A route `loader` redirects to 403.

## 6. Folder Structure

```
frontend/
├── CLAUDE.md                      # CRMS UI agent rules (provided)
├── .claude/skills/crms-theme-style-guide/SKILL.md
├── index.html
├── vite.config.ts · tailwind.config.ts · tsconfig.json
├── public/
└── src/
    ├── main.tsx
    ├── app/
    │   ├── router.tsx             # route tree + role loaders
    │   ├── providers.tsx          # QueryClient, SSE provider, Theme
    │   └── layout/                # AppShell: CRMS sidebar, header (user, role badge, sign out), content
    ├── api/
    │   ├── client.ts              # ky + auth/refresh interceptor, problem+json → ApiError
    │   ├── schema.d.ts            # generated (openapi-typescript)
    │   └── realtime.ts            # SSE stream per dataset (fetch + eventsource-parser), Last-Event-ID resume, event → query invalidation
    ├── auth/
    │   ├── session.store.ts       # Zustand: accessToken, user, role
    │   ├── permissions.ts         # role → permission map (mirrors wireframe 1c)
    │   ├── Can.tsx · RequireRole.tsx
    │   └── pages/ LoginPage.tsx · AcceptInvitePage.tsx
    ├── features/
    │   ├── datasets/   { api.ts, schemas.ts, components/, pages/DatasetsPage.tsx, pages/DatasetProfilePage.tsx }
    │   ├── plans/      { api.ts, schemas.ts, components/StepTable.tsx, components/StepDiffDrawer.tsx, pages/PlanReviewPage.tsx }
    │   ├── runs/       { api.ts, components/TestSummary.tsx, components/VersionTimeline.tsx, components/RollbackModal.tsx, pages/RunPage.tsx }
    │   ├── model-config/ { api.ts, schemas.ts, pages/ModelSettingsPage.tsx }
    │   ├── users/      { api.ts, schemas.ts, components/InviteUserModal.tsx, pages/UsersPage.tsx }
    │   ├── audit/      { api.ts, components/AuditFilters.tsx, pages/AuditPage.tsx }
    │   └── evaluation/ { api.ts, pages/EvaluationPage.tsx }
    ├── shared/
    │   ├── ui/                    # CRMS patterns only: Button, Card, KpiCard, Badge, DataTable, Modal, Drawer,
    │   │                          # FormField, Input, Select, RadioGroup, Checkbox, FileDrop, DatePicker, Toast, EmptyState
    │   ├── hooks/                 # useDebounce, usePagination, useJobStatus
    │   ├── lib/                   # format.ts (dates, numbers, %), download.ts
    │   └── constants/             # messages.ts (all user-facing strings in one place)
    ├── pages/ Forbidden.tsx · NotFound.tsx
    └── test/  msw/handlers.ts · setup.ts
e2e/ (Playwright) login.spec.ts · clean-dataset.spec.ts · rollback.spec.ts · rbac.spec.ts
```

---

## 7. Screen Requirements

All labels are top-aligned. Mandatory fields have a red `*`. Numbers are right-aligned in tables. Dates use `dd-MM-yyyy` and times `dd-MM-yyyy HH:mm`, 24 h, in the user's local timezone. Audit timestamps are in UTC (OQ-22). All message strings live in `shared/constants/messages.ts` exactly as written below.

### S1 Login (1a)
| Field | Control | Rules | Message |
|---|---|---|---|
| Work email * | Input email | email format, max 254 | "Enter a valid work email address." |
| Password * | Input password + Show/Hide | 12–128 chars | "Enter your password." |
| Sign in | Primary button | disabled while submitting | 401 → "Email or password is incorrect." · 423 → "Your account is locked. Try again in 15 minutes." · 403 inactive → "Your account is inactive. Contact an Administrator." |

On success the user goes to the role's landing route (§2). `?expired=1` shows the banner "Your session expired. Please sign in again."

### S2 Accept invite
Fields: New password * (12–128), Confirm password * (must match: "Passwords must match."). The Set password button logs the user in and redirects.

### S3 Datasets (1d)
- **Grid:** Name (link), Source, Rows (R), Cols (R), Ingested (sort desc by default), Status badge. Page size 20. Filter by status. Search by name, debounced 300 ms.
- **Status badge colours (CRMS pill):** Profiling = info, Plan ready = warning, Approved/Executed = success, Tests failed/Failed = danger, Rolled back = secondary.
- **Upload modal** (Data Engineer only): Source radio (default Upload file; n8n folder shows a read-only path from config), File drop (.xlsx/.csv, max from `GET /config/upload`), Dataset name (3–80, `[A-Za-z0-9 _.-]`, defaults to the file name without extension). Upload & profile → `POST /datasets` shows an upload progress bar, then closes the modal and prepends the row with status "Profiling". Row status then updates live via SignalR.
- **Empty state:** "No datasets yet. Upload a file or connect the n8n output folder."

### S4 Profile (1e)
- KPI cards (CRMS white card + icon): Rows, Columns, Columns with nulls, Nested columns, Quarantined rows.
- Profile grid: Column, Physical type, Semantic type, Null % (0 dp), Distinct, Flags (danger badges). Clicking a row expands min/max/mean.
- Inferred rules list: expression, confidence (2 dp). Evidence link opens a modal with up to 10 rows.
- Quarantine banner if > 0: "{n} rows were quarantined during ingest. View rows". The link opens a drawer with row ref + reason.
- **Generate plan** button (Data Engineer): `POST /datasets/{id}/plans`. The button shows a spinner and "Generating plan…" until the `PlanGenerated` event arrives, then navigates to S5. On `JobFailed` it shows a toast "Plan generation failed: {message}" with a Retry button.

### S5 Plan review (1f + 1g)
- Header: total estimated loss ("Total est. loss: 0.4% of cells", OQ-23). Threshold banner if any step is over the threshold: "Step {n} exceeds the loss threshold and needs a decision before approval."
- **Step table:** #, Operation (plain-language summary from the API), Cells (R), Loss (R; "High" badge if over the threshold), Decision radio (Accept / Edit / Reject). Steps at or under the threshold default to Accept; steps over it start with no decision.
- **Row click → right drawer (1g):** rationale, confidence, before/after sample (≤ 5 rows, changed cells highlighted), loss bar.
- **Edit** opens a modal with the step parameters, using a form generated per operation type from the Zod schema. **Reject** asks for a reason (10–500 chars: "Enter a reason of at least 10 characters.").
- Each decision is saved immediately with `PATCH` (optimistic update, rollback on error).
- **Approve plan** is disabled until every step is decided; the label shows "Approve plan ({decided} of {total} decided)". It opens a confirm modal: "Approve {n} steps? Unit and integration tests will be generated." On confirm it calls `POST /approve` then `POST /execute` and navigates to S6.
- **Regenerate plan** asks for confirmation: "This replaces the current plan and clears your decisions."
- Read-only for Auditor/Viewer: radios, Edit, Reject and Approve are hidden, and the drawer still works.

### S6 Run, tests, rollback (1i)
- A live progress list per step (from `JobStatusChanged`), then the results.
- Test tiles: Unit passed/total, Integration passed/total. Clicking one opens the test list (name, target step, result, run time).
- Reconciliation grid: Check, Source (R), Output (R), OK.
- Export buttons: XLSX, CSV, Pipeline (JSON). **Hidden** if tests failed, with the banner "Export is blocked because 1 or more tests failed." Clicking an export calls `POST /exports` and downloads from the pre-signed URL.
- Version timeline: newest first, v0 labelled "Original (immutable)". Each row except the current one has "Roll back here" (Data Engineer).
- Rollback modal: "Roll back to v{n}? Steps {a}–{b} will be undone. The rollback is itself logged and can be re-applied." Reason * (10–500). Roll back → `POST /rollback`; the screen then refreshes on `RollbackCompleted`.

### S7 Model settings (1j)
| Field | Control | Rules |
|---|---|---|
| Provider * | Select, **dynamic** (`GET /model-config/providers`) | changing it clears Model |
| Model * | Select, dynamic per provider | — |
| API key * | Password input showing `•••• last4` + Replace | 20–200 chars; required on first save only |
| Endpoint URL | Input | optional, `https://` only, max 2048 · "Enter a valid https URL." |
| Allow dataset values to be sent to this provider | Checkbox | default off · helper text: "When off, only column names and statistics are sent." |

**Test connection** shows an inline success message ("Connection OK · {ms} ms") or error. **Save** runs the test first; on failure it shows "Could not reach the provider. Check the key and endpoint." and doesn't save.

### S8 Users & roles (1k)
Grid: User (name + email), Role, Status, Last sign-in, and an actions menu (Change role, Deactivate). **Invite user** modal: Email * (unique: "This user already exists."), Role * (static: Data Engineer, Administrator, Auditor, Viewer). Deactivate asks for confirmation: "Deactivate this user? They will be signed out." Admins can't deactivate themselves (the action is hidden on their own row).

### S9 Audit trail (1l)
Filters: From/To date (To ≥ From: "End date must be on or after start date."), Event type multi-select (static list), User select (dynamic). The filters are synced to the URL query. Grid: Timestamp UTC (sort desc), User, Role, Event, Object (link). 50 per page. **Export CSV** (Auditor only) exports the current filter result. Empty state: "No events match these filters."

### S10 Evaluation
Table of runs (benchmark set, model, started, duration, pass rate). "Run evaluation" opens a modal with Benchmark set * (dynamic select). Results appear live via SSE.

---

## 8. Cross-cutting Requirements

| Area | Requirement |
|---|---|
| Theme | Follows CRMS CLAUDE.MD exactly: Nunito Sans, page `bg-[#f2f3f7]`, cards `bg-white rounded-lg border border-[#e9ecef]`, primary `bg-[#fd6321]`, active sidebar item `bg-[#fd6321] text-white`, `dark:` variant on every colour class, Tabler icons 14–20 px. The wireframes are low-fi; the CRMS theme wins where they differ. |
| Errors | `ApiError` is built from the problem+json `code`. Field errors show inline under the field. Other errors show a toast using the backend message. Network loss shows the banner "You're offline. Changes will retry when you reconnect." |
| Loading | Skeletons for tables and cards. No layout shift after data arrives. Buttons show a spinner and are disabled while their mutation is pending. |
| Real-time | Open the SSE stream `GET /datasets/{id}/events` on S4–S6 and close it on unmount. Auto-reconnect with backoff (0, 2, 5, 10, 30 s), sending `Last-Event-ID` so missed events are replayed. After reconnect, refetch the active queries. |
| Session | Idle timeout 30 min (**assumed**, OQ-18), with a warning modal 2 min before. Sign out clears the query cache and store. |
| Accessibility | WCAG 2.1 AA: keyboard reachable, visible focus (`focus:ring-[#fd6321]`), labelled inputs, table headers with `scope`, modals trap focus and close on Esc, colour is never the only signal (badges have text). |
| Performance | Initial JS < 250 KB gzip. Routes are lazy-loaded. Tables over 200 rows use virtualised rows. LCP < 2.5 s on the office network. |
| Security | No tokens in localStorage. CSP from nginx (`default-src 'self'`, `connect-src` API origin). Dataset values from the API are always rendered as text, never as HTML (FR-045). |
| i18n | English only for MVP, but every string goes through `messages.ts` so it can be translated later. |
| Browser support | Latest 2 versions of Chrome, Edge, Firefox; min width 1024 px. |

## 9. Acceptance Criteria (MVP)

1. A Data Engineer can take `Append_to_Reconciliation_Sheet.xlsx` from upload to export without leaving the app. The export has 22 InvoiceSummary rows and 313 LineItems rows, and the reconciliation grid shows the gross total 154,292 as matched.
2. Each role sees only the nav items and actions in §2. Playwright `rbac.spec.ts` checks every route for every role, including a direct URL giving 403.
3. Approve is impossible while any step is undecided, and export is impossible while any test fails (UI hides the action; API returns 409).
4. Job progress for profile, plan, execute, validate and rollback appears within 2 s of the backend event, with no page refresh.
5. Rolling back to v0 restores the original row count and columns exactly.
6. Every message string on screen matches this PRD word for word.
7. Lighthouse accessibility score ≥ 95 on S3–S6.

## 10. Open Questions (frontend impact)

OQ-03 who approves · OQ-04 threshold value · OQ-09 max upload size · OQ-17 MFA · OQ-18 session timeout (30 min assumed) · OQ-19 SSO · OQ-20 Viewer role · OQ-21 one role per user · OQ-22 date format (dd-MM-yyyy assumed) · OQ-23 loss unit (% of cells assumed).
