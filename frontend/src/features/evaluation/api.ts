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
  run: Pick<EvaluationRun, "finishedAt"> | null | undefined
): boolean {
  if (!run) return false;
  return !run.finishedAt;
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
    queryFn: () => api.get("evaluations").json<EvaluationRun[]>(),
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
    queryFn: () => api.get(`evaluations/${id}`).json<EvaluationRunDetail>(),
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
      return api.post("evaluations", { json: body }).json<EvaluationRun>();
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
