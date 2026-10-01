import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import type {
  EvaluationRun,
  EvaluationRunDetail,
  StartEvaluationRequest,
} from "../../api/schema";
import {
  MSG_EVALUATION_START_FAILED,
} from "../../shared/constants/messages";

/**
 * S10 Evaluation server state (PRD Section 7, wireframe 1m).
 *
 * Runs are asynchronous: the backend returns as soon as the job is queued and
 * fills the scores in later. The list is polled only while a run is still
 * going — dataset SSE is not used here, because an evaluation is not a dataset
 * (PRD Section 6).
 */

/** The two benchmark sets configured for this environment (PRD S10). */
export const BENCHMARK_SET_OPTIONS = [
  { value: "vendor-invoices-golden", label: "vendor-invoices-golden" },
  { value: "adversarial-pack", label: "adversarial-pack" },
] as const;

export const BENCHMARK_SET_IDS: string[] = BENCHMARK_SET_OPTIONS.map(
  (option) => option.value
);

export type BenchmarkSetId = (typeof BENCHMARK_SET_OPTIONS)[number]["value"];

export const DEFAULT_BENCHMARK_SET: BenchmarkSetId = "vendor-invoices-golden";

export const evaluationKeys = {
  all: ["evaluations"] as const,
  list: ["evaluations", "list"] as const,
  detail: (id: string) => ["evaluations", "detail", id] as const,
};

/** How often a run that has not finished is re-read. */
export const EVALUATION_POLL_MS = 2_000;

/**
 * A run is finished once the backend stamps `finishedAt`. There is no separate
 * status field on the contract.
 */
export function isEvaluationRunning(
  run: Pick<EvaluationRun, "finishedAt" | "status"> | null | undefined
): boolean {
  // A failed run may never get finishedAt; its status still ends the polling.
  if (run?.status === "succeeded" || run?.status === "failed") return false;
  if (!run) return false;
  return !run.finishedAt;
}

interface RawCase {
  caseId: string;
  crashed?: boolean;
  error?: string | null;
  failures?: unknown[];
  rowCount?: number;
  durationMs?: number;
}

/**
 * API -> view model. The backend sends `scores = { checks, cases, passed, llm_on }`;
 * the screen shows a pass rate (share of benchmark cases with no failures), a
 * duration, and one result row per case.
 */
export function toEvaluationRun(raw: EvaluationRunDetail): EvaluationRunDetail {
  const scores = (raw.scores ?? {}) as {
    cases?: RawCase[];
    passed?: boolean;
    llm_on?: boolean;
  };
  const cases = Array.isArray(scores.cases) ? scores.cases : [];
  const ok = cases.filter((c) => !c.crashed && (c.failures?.length ?? 0) === 0).length;
  const start = raw.startedAt ? Date.parse(raw.startedAt) : NaN;
  const end = raw.finishedAt ? Date.parse(raw.finishedAt) : NaN;
  return {
    ...raw,
    benchmarkSetName:
      raw.benchmarkSetName ?? (cases.length ? `Labelled benchmark (${cases.length} cases)` : undefined),
    modelName: raw.modelName ?? (scores.llm_on ? "AI on" : "Deterministic (AI off)"),
    passRate: raw.passRate ?? (cases.length ? ok / cases.length : undefined),
    durationSeconds:
      raw.durationSeconds ?? (Number.isFinite(start) && Number.isFinite(end) ? (end - start) / 1000 : undefined),
    passed: raw.passed ?? scores.passed,
    detailedResults:
      raw.detailedResults ??
      cases.map((c) => ({
        case: c.caseId,
        result: c.crashed ? "crashed" : (c.failures?.length ?? 0) === 0 ? "passed" : "failed",
        rows: c.rowCount ?? 0,
        details: c.error ?? (c.failures ?? []).map(String).join("; "),
      })),
  };
}

/** GET /evaluations answers a page `{ items, ... }`; older builds sent a bare array. */
function toEvaluationRuns(raw: { items: EvaluationRunDetail[] } | EvaluationRunDetail[]): EvaluationRun[] {
  return (Array.isArray(raw) ? raw : raw.items ?? []).map(toEvaluationRun);
}

/**
 * GET /evaluations — every run, newest first.
 *
 * Re-read every couple of seconds while any run is still going, so a run that
 * was started on another screen settles here on its own.
 */
export function useEvaluations(): UseQueryResult<EvaluationRun[], ApiError> {
  return useQuery<EvaluationRun[], ApiError>({
    queryKey: evaluationKeys.list,
    queryFn: async () =>
      toEvaluationRuns(
        await api.get("evaluations").json<{ items: EvaluationRunDetail[] } | EvaluationRunDetail[]>()
      ),
    refetchInterval: (query) => {
      const runs = query.state.data;
      return Array.isArray(runs) && runs.some(isEvaluationRunning)
        ? EVALUATION_POLL_MS
        : false;
    },
  });
}

/**
 * GET /evaluations/{id}, polled while the run is still going so the pass rate
 * and duration fill in without a page reload.
 */
export function useEvaluation(
  id: string | null
): UseQueryResult<EvaluationRunDetail, ApiError> {
  return useQuery<EvaluationRunDetail, ApiError>({
    queryKey: evaluationKeys.detail(id ?? ""),
    queryFn: async () =>
      toEvaluationRun(await api.get(`evaluations/${id}`).json<EvaluationRunDetail>()),
    enabled: Boolean(id),
    refetchInterval: (query) =>
      isEvaluationRunning(query.state.data) ? EVALUATION_POLL_MS : false,
  });
}

export interface StartEvaluationVariables {
  benchmarkSet: string;
}

/** The wire body the S10 screen is specified to post. */
export interface StartEvaluationWireBody {
  benchmarkSet: string;
}

export type UseStartEvaluationResult = UseMutationResult<
  EvaluationRun,
  ApiError,
  StartEvaluationVariables
>;

/**
 * POST /evaluations — queues a run.
 *
 * Backend confirmed (2026-09-30 integration): accepts both `benchmarkSet`
 * (name slug, resolved server-side) and `benchmarkSetId` (UUID).
 * Remaining: regenerate `StartEvaluationRequest` in `src/api/schema.d.ts`
 * from the live OpenAPI spec, at which point this cast can go.
 */
export function useStartEvaluation(): UseStartEvaluationResult {
  const queryClient = useQueryClient();

  return useMutation<EvaluationRun, ApiError, StartEvaluationVariables>({
    mutationFn: async ({ benchmarkSet }) => {
      const body = { benchmarkSet } as unknown as StartEvaluationRequest;
      return toEvaluationRun(
        await api.post("evaluations", { json: body }).json<EvaluationRunDetail>()
      );
    },
    onSuccess: (run) => {
      // Seed the detail cache so the modal shows the run immediately, then let
      // the poller take over.
      if (run?.id) {
        queryClient.setQueryData(evaluationKeys.detail(run.id), run);
      }
      void queryClient.invalidateQueries({ queryKey: evaluationKeys.list });
    },
  });
}

/** Message shown when a run cannot be started. */
export function startEvaluationErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.detail || error.title || MSG_EVALUATION_START_FAILED;
  }
  return MSG_EVALUATION_START_FAILED;
}
