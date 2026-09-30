import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import type {
  ExportFormat,
  ExportResponse,
  ReconciliationCheck,
  RollbackResult,
  TestCaseType,
  TestRunResult,
} from "../../api/schema";
import {
  MSG_ENTER_REASON_MIN_10,
  MSG_EXPORT_BLOCKED_TESTS_FAILED,
  MSG_EXPORT_FAILED,
  MSG_JOB_ALREADY_RUNNING,
  MSG_ORIGINAL_IMMUTABLE,
} from "../../shared/constants/messages";
import { downloadFromUrl } from "../../shared/lib/download";

/**
 * S6 (Run, tests, versions, rollback) server state — PRD Section 7, wireframe 1i.
 *
 * Thin, typed layer over the ky client, exactly like features/plans/api.ts: the
 * hooks return data only and never hold server state. The SSE stream
 * (src/api/realtime.ts) invalidates these same keys, so the screen refreshes on
 * `RollbackCompleted` and `ValidationCompleted` without polling.
 */

/**
 * Query key namespaces. `PLAN_KEY` mirrors `PLAN_KEY` in features/plans/api.ts;
 * realtime.ts also invalidates the "plans" prefix, so both are invalidated on a
 * rollback. The dataset keys mirror features/datasets/api.ts.
 */
export const VALIDATION_KEY = "validation";
export const VERSIONS_KEY = "versions";
export const PLAN_KEY = "plan";
export const PLANS_KEY = "plans";
export const DATASET_KEY = "dataset";
export const DATASETS_KEY = "datasets";

/** problem+json code the backend answers with when the export gate is closed (FR-043). */
export const EXPORT_BLOCKED_CODE = "EXPORT_BLOCKED_TESTS_FAILED";

/** Fallback for an export failure the mapping below does not recognise. */
export const EXPORT_FAILED_MESSAGE = MSG_EXPORT_FAILED;
/** Fallback for a rollback failure the mapping below does not recognise. */
export const ROLLBACK_FAILED_MESSAGE = "The rollback could not be started. Please try again.";

/** v0 is the untouched original: it is never overwritten, only restored. */
export const ORIGINAL_VERSION_NO = 0;

const REASON_REQUIRED_CODE = "REASON_REQUIRED";

// -----------------------------------------------------------------------------
// View models
// -----------------------------------------------------------------------------

/** The two generated suites (PRD S6 tiles). */
export type TestSuite = TestCaseType;

/**
 * Result of one test. `not_run` is display-only: it means the API returned the
 * test definition without a run record yet, and it is never counted as a pass.
 */
export type TestOutcome = TestRunResult | "not_run";

/** One row of the expandable test list (name, target step, result, run time). */
export interface TestRunRow {
  id: string;
  name: string;
  suite: TestSuite;
  targetStepNo: number | null;
  outcome: TestOutcome;
  durationMs: number | null;
}

export interface TestSuiteSummary {
  passed: number;
  total: number;
  tests: TestRunRow[];
}

/** PRD S6 reconciliation grid row. */
export type ReconRow = ReconciliationCheck;

export interface Validation {
  unit: TestSuiteSummary;
  integration: TestSuiteSummary;
  reconciliation: ReconRow[];
  /** Latest validation run for this version passed — the export gate (FR-043). */
  latestPassed: boolean;
}

/** One row of the version timeline (PRD S6). */
export interface Version {
  n: number;
  createdAt: string | null;
  rows: number | null;
  cols: number | null;
  isCurrent: boolean;
  label?: string;
}

// -----------------------------------------------------------------------------
// Shape adapters
// -----------------------------------------------------------------------------

interface RawSummary {
  passed?: number | null;
  total?: number | null;
}

interface RawSuiteSummary extends RawSummary {
  tests?: unknown;
}

interface RawTest {
  id?: string;
  testCaseId?: string;
  name?: string;
  testCaseName?: string;
  suite?: unknown;
  type?: unknown;
  targetStepNo?: number | null;
  outcome?: unknown;
  result?: unknown;
  durationMs?: number | null;
}

interface RawValidation {
  unit?: RawSuiteSummary | null;
  integration?: RawSuiteSummary | null;
  unitSummary?: RawSummary | null;
  integrationSummary?: RawSummary | null;
  testRuns?: unknown;
  testCases?: unknown;
  reconciliation?: unknown;
  reconciliations?: unknown;
  latestPassed?: boolean | null;
  allPassed?: boolean | null;
}

interface RawVersion {
  n?: number | null;
  versionNo?: number | null;
  createdAt?: string | null;
  executedAt?: string | null;
  rows?: number | null;
  cols?: number | null;
  rowCount?: number | null;
  columnCount?: number | null;
  isCurrent?: boolean | null;
  current?: boolean | null;
  label?: string | null;
}

const UNTITLED_TEST = "Unnamed test";
const TEST_RESULTS: readonly string[] = ["passed", "failed", "error"];

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function toBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function toArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function firstArray(...values: unknown[]): unknown[] {
  for (const value of values) {
    if (Array.isArray(value)) return value;
  }
  return [];
}

function toSuite(value: unknown, fallback: TestSuite): TestSuite {
  return value === "unit" || value === "integration" ? value : fallback;
}

function toOutcome(value: unknown): TestOutcome {
  return typeof value === "string" && TEST_RESULTS.includes(value)
    ? (value as TestRunResult)
    : "not_run";
}

/**
 * One test row from either a test-case definition or a test run. The run carries
 * the result and the duration; the case carries the name and the target step, so
 * the two are merged on `testCaseId`.
 */
function toTestRow(raw: RawTest, index: number, fallbackSuite: TestSuite): TestRunRow {
  return {
    id: raw.testCaseId ?? raw.id ?? `${fallbackSuite}-test-${index}`,
    name: raw.name ?? raw.testCaseName ?? UNTITLED_TEST,
    suite: toSuite(raw.suite ?? raw.type, fallbackSuite),
    targetStepNo: toNumber(raw.targetStepNo),
    outcome: toOutcome(raw.outcome ?? raw.result),
    durationMs: toNumber(raw.durationMs),
  };
}

function mergeTestRows(
  cases: unknown,
  runs: unknown,
  fallbackSuite: TestSuite
): TestRunRow[] {
  const rows = new Map<string, TestRunRow>();

  for (const [index, raw] of toArray(cases).entries()) {
    const row = toTestRow((raw ?? {}) as RawTest, index, fallbackSuite);
    rows.set(row.id, row);
  }

  for (const [index, raw] of toArray(runs).entries()) {
    const row = toTestRow((raw ?? {}) as RawTest, index, fallbackSuite);
    const existing = rows.get(row.id);
    if (!existing) {
      rows.set(row.id, row);
      continue;
    }
    rows.set(row.id, {
      id: existing.id,
      name: existing.name === UNTITLED_TEST ? row.name : existing.name,
      suite: existing.suite === fallbackSuite ? row.suite : existing.suite,
      targetStepNo: existing.targetStepNo ?? row.targetStepNo,
      outcome: existing.outcome === "not_run" ? row.outcome : existing.outcome,
      durationMs: existing.durationMs ?? row.durationMs,
    });
  }

  return [...rows.values()];
}

/** Run records for one suite; an unlabelled run is assumed to belong to it. */
function runsForSuite(runs: unknown[], suite: TestSuite): unknown[] {
  return runs.filter((run) => {
    const record = (run ?? {}) as RawTest;
    const declared = record.type ?? record.suite;
    return declared === undefined || declared === null || toSuite(declared, suite) === suite;
  });
}

function suiteFrom(
  suite: RawSuiteSummary | null | undefined,
  summary: RawSummary | null | undefined,
  cases: unknown[],
  runs: unknown[],
  fallbackSuite: TestSuite
): TestSuiteSummary {
  // Tile shape: the suite carries its own `tests`. Contract shape: the runs live
  // at the top level and are split by `type`. Merging on id is safe for both.
  const caseList = firstArray(suite?.tests, casesForSuite(cases, fallbackSuite));
  const tests = mergeTestRows(caseList, runsForSuite(runs, fallbackSuite), fallbackSuite);

  const total = toNumber(summary?.total ?? suite?.total) ?? tests.length;
  const passed =
    toNumber(summary?.passed ?? suite?.passed) ??
    tests.filter((row) => row.outcome === "passed").length;

  return { passed, total, tests };
}

function casesForSuite(cases: unknown[], suite: TestSuite): unknown[] {
  return cases.filter((entry) => {
    const record = (entry ?? {}) as RawTest;
    const declared = record.type ?? record.suite;
    return declared === undefined || declared === null || toSuite(declared, suite) === suite;
  });
}

function toReconciliation(raw: unknown, index: number): ReconRow {
  const record = (raw ?? {}) as Partial<ReconciliationCheck>;
  const sourceValue = record.sourceValue;
  const outputValue = record.outputValue;

  return {
    id: typeof record.id === "string" && record.id !== "" ? record.id : `recon-${index}`,
    planId: typeof record.planId === "string" ? record.planId : "",
    versionNo: toNumber(record.versionNo) ?? 0,
    checkName:
      typeof record.checkName === "string" && record.checkName !== ""
        ? record.checkName
        : "Check",
    sourceValue:
      typeof sourceValue === "number" || typeof sourceValue === "string" ? sourceValue : "",
    outputValue:
      typeof outputValue === "number" || typeof outputValue === "string" ? outputValue : "",
    // An absent `ok` is treated as a mismatch: the grid never claims a match the
    // server did not report, and the export gate below stays consistent with it.
    ok: toBoolean(record.ok) ?? false,
  };
}

function suitesAllPassed(
  suites: TestSuiteSummary[],
  reconciliation: ReconRow[]
): boolean {
  const testsPassed = suites.every(
    (suite) => suite.total === 0 || suite.passed >= suite.total
  );
  const reconciles = reconciliation.every((row) => row.ok);
  return testsPassed && reconciles;
}

/**
 * GET /plans/{id}/validation → the S6 view model.
 * Accepts the tile shape (`unit.tests`), the contract shape
 * (`unitSummary` + `testRuns` + `testCases` + `reconciliations`), or both.
 */
export function toValidation(raw: unknown): Validation {
  const record = (raw ?? {}) as RawValidation;

  const runs = toArray(record.testRuns);
  const cases = toArray(record.testCases);

  const unit = suiteFrom(record.unit, record.unitSummary, cases, runs, "unit");
  const integration = suiteFrom(
    record.integration,
    record.integrationSummary,
    cases,
    runs,
    "integration"
  );
  const reconciliation = firstArray(record.reconciliation, record.reconciliations).map(
    toReconciliation
  );

  const latestPassed =
    toBoolean(record.latestPassed) ??
    toBoolean(record.allPassed) ??
    suitesAllPassed([unit, integration], reconciliation);

  return { unit, integration, reconciliation, latestPassed };
}

function toVersion(raw: RawVersion, index: number): Version {
  const n = toNumber(raw.n ?? raw.versionNo) ?? index;
  const label = raw.label ?? undefined;

  return {
    n,
    createdAt: raw.createdAt ?? raw.executedAt ?? null,
    rows: toNumber(raw.rows ?? raw.rowCount),
    cols: toNumber(raw.cols ?? raw.columnCount),
    isCurrent: toBoolean(raw.isCurrent ?? raw.current) ?? false,
    label,
  };
}

function versionList(raw: unknown): unknown[] {
  const record = (raw ?? {}) as { versions?: unknown; items?: unknown };
  return Array.isArray(raw) ? raw : firstArray(record.versions, record.items);
}

/**
 * GET /plans/{id}/versions → newest first.
 * v0 (the immutable original) is added when the endpoint omits it, because the
 * PRD timeline requires the row and rolling back to it must stay possible. Its
 * shape figures stay `null` (rendered "—") rather than being invented.
 */
export function toVersions(raw: unknown): Version[] {
  const versions = versionList(raw).map((entry, index) =>
    toVersion((entry ?? {}) as RawVersion, index)
  );

  if (!versions.some((version) => version.n === ORIGINAL_VERSION_NO)) {
    versions.push({
      n: ORIGINAL_VERSION_NO,
      createdAt: null,
      rows: null,
      cols: null,
      isCurrent: false,
      label: MSG_ORIGINAL_IMMUTABLE,
    });
  }

  const sorted = [...versions].sort((a, b) => b.n - a.n);

  // When the endpoint flags no current version the newest one is the live output.
  if (!sorted.some((version) => version.isCurrent) && sorted.length > 0) {
    const newest = sorted[0].n;
    return sorted.map((version) =>
      version.n === newest ? { ...version, isCurrent: true } : version
    );
  }

  return sorted;
}

// -----------------------------------------------------------------------------
// Errors
// -----------------------------------------------------------------------------

/**
 * 409 EXPORT_BLOCKED_TESTS_FAILED → the PRD banner copy (PRD Section 7, S6).
 * The buttons are already hidden in that state; this covers a validation run
 * that failed between the last fetch and the click.
 */
export function mapExportError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === EXPORT_BLOCKED_CODE || (error.status === 409 && !error.code)) {
      return MSG_EXPORT_BLOCKED_TESTS_FAILED;
    }
    return error.detail || error.title;
  }
  if (error instanceof Error && error.message) return error.message;
  return EXPORT_FAILED_MESSAGE;
}

/** Maps a rollback failure onto the messages.ts copy / the backend message. */
export function mapRollbackError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 400 && error.code === REASON_REQUIRED_CODE) {
      return MSG_ENTER_REASON_MIN_10;
    }
    if (error.status === 409 && error.code === "JOB_ALREADY_RUNNING") {
      return MSG_JOB_ALREADY_RUNNING;
    }
    return error.detail || error.title;
  }
  if (error instanceof Error && error.message) return error.message;
  return ROLLBACK_FAILED_MESSAGE;
}

// -----------------------------------------------------------------------------
// Queries
// -----------------------------------------------------------------------------

export function validationQueryKey(planId: string) {
  return [VALIDATION_KEY, planId] as const;
}

export function versionsQueryKey(planId: string) {
  return [VERSIONS_KEY, planId] as const;
}

/** GET /plans/{id}/validation — test tiles, test list, reconciliation, gate flag. */
export function useValidation(planId: string | undefined): UseQueryResult<Validation, ApiError> {
  return useQuery<Validation, ApiError>({
    queryKey: validationQueryKey(planId ?? ""),
    enabled: Boolean(planId),
    queryFn: async ({ signal }) => {
      const raw = await api.get(`plans/${planId}/validation`, { signal }).json<unknown>();
      return toValidation(raw);
    },
  });
}

/** GET /plans/{id}/versions — version timeline, newest first. */
export function useVersions(planId: string | undefined): UseQueryResult<Version[], ApiError> {
  return useQuery<Version[], ApiError>({
    queryKey: versionsQueryKey(planId ?? ""),
    enabled: Boolean(planId),
    queryFn: async ({ signal }) => {
      const raw = await api.get(`plans/${planId}/versions`, { signal }).json<unknown>();
      return toVersions(raw);
    },
  });
}

// -----------------------------------------------------------------------------
// Mutations
// -----------------------------------------------------------------------------

export interface RollbackVariables {
  planId: string;
  /** Version number to restore. */
  version: number;
  /** 10–500 characters; written to the audit trail. */
  reason: string;
  /** Known by the page (from the plan) so the dataset row is refreshed too. */
  datasetId?: string;
}

export type UseRollbackResult = UseMutationResult<
  RollbackResult,
  ApiError,
  RollbackVariables
>;

function invalidateAfterRollback(
  queryClient: ReturnType<typeof useQueryClient>,
  { planId, datasetId }: RollbackVariables
): void {
  void queryClient.invalidateQueries({ queryKey: versionsQueryKey(planId) });
  void queryClient.invalidateQueries({ queryKey: validationQueryKey(planId) });
  void queryClient.invalidateQueries({ queryKey: [PLAN_KEY, planId] });
  void queryClient.invalidateQueries({ queryKey: [PLANS_KEY, planId] });
  if (datasetId) {
    void queryClient.invalidateQueries({ queryKey: [DATASET_KEY, datasetId] });
    void queryClient.invalidateQueries({ queryKey: [DATASETS_KEY, datasetId] });
  }
}

/**
 * POST /plans/{id}/rollback — queues the rollback job. The screen then refreshes
 * on the `RollbackCompleted` SSE event; the invalidations below make the queued
 * state consistent straight away.
 */
export function useRollback(): UseRollbackResult {
  const queryClient = useQueryClient();

  return useMutation<RollbackResult, ApiError, RollbackVariables>({
    mutationFn: ({ planId, version, reason }) =>
      api
        .post(`plans/${planId}/rollback`, { json: { version, reason } })
        .json<RollbackResult>(),
    onSuccess: (_result, variables) => {
      invalidateAfterRollback(queryClient, variables);
    },
  });
}

const EXPORT_EXTENSIONS: Record<ExportFormat, string> = {
  xlsx: "xlsx",
  csv: "csv",
  pipeline: "json",
};

export interface ExportVariables {
  planId: string;
  format: ExportFormat;
  /** Used for the download file name; the plan id is the fallback. */
  datasetName?: string;
}

export type UseExportResult = UseMutationResult<
  ExportResponse,
  ApiError,
  ExportVariables
>;

/** `{dataset name}-v{n}.xlsx` (pipeline exports are JSON). */
export function exportFileName(
  { planId, format, datasetName }: ExportVariables,
  response?: Pick<ExportResponse, "versionNo">
): string {
  const rawBase = (datasetName ?? planId).trim() || planId;
  const base = rawBase.replace(/[^A-Za-z0-9 _.-]/g, "_");
  const versionNo = toNumber(response?.versionNo);
  const version = versionNo === null ? "" : `-v${versionNo}`;
  return `${base}${version}.${EXPORT_EXTENSIONS[format] ?? "csv"}`;
}

/**
 * POST /plans/{id}/exports → `{ downloadUrl }` (pre-signed, 15 min). The file is
 * fetched through the shared download helper so the Bearer token and the cookie
 * are sent instead of handing a bare pre-signed link to the browser.
 */
export function useExport(): UseExportResult {
  return useMutation<ExportResponse, ApiError, ExportVariables>({
    mutationFn: async (variables) => {
      const response = await api
        .post(`plans/${variables.planId}/exports`, { json: { format: variables.format } })
        .json<ExportResponse>();

      await downloadFromUrl(response.downloadUrl, exportFileName(variables, response));
      return response;
    },
  });
}