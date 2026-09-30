import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import type {
  ApprovePlanResponse,
  LossEstimate,
  PlanDetail,
  PlanStep,
  StepDecision,
} from "../../api/schema";
import {
  MSG_DECIDE_EVERY_STEP,
  MSG_ENTER_REASON_MIN_10,
} from "../../shared/constants/messages";
import {
  API_TO_DECISION,
  toApiDecision,
  type DecisionChoice,
  type EditParams,
} from "./schemas";

export const PLAN_KEY = "plan";

export function planQueryKey(planId: string) {
  return [PLAN_KEY, planId] as const;
}

// -----------------------------------------------------------------------------
// Shape adapters
// -----------------------------------------------------------------------------

/**
 * The loss breakdown for a step, or null when the API has not estimated it.
 * Reads the generated contract field first and falls back to the wire field the
 * FastAPI planning schema emits (`estimatedLoss`, nullable).
 */
export function getStepLossEstimate(step: PlanStep): LossEstimate | null {
  const wire = step as PlanStep & { estimatedLoss?: LossEstimate | null };
  return step.lossEstimate ?? wire.estimatedLoss ?? null;
}

/**
 * The backend stores ratios as fractions (0.05 = 5%). The UI shows percent, so
 * every displayed figure is converted here.
 */
export function fractionToPct(fraction: number | null | undefined): number {
  if (fraction === null || fraction === undefined || isNaN(fraction)) return 0;
  return Math.round(fraction * 100 * 100) / 100;
}

/**
 * Two-decimal percent, as the PRD requires for loss and confidence figures.
 * `formatPct` in shared/lib/format drops trailing zeros, so it cannot be used.
 */
export function formatPct2dp(value: number): string {
  return `${value.toFixed(2)}%`;
}

export function getStepLossPct(step: PlanStep): number {
  return fractionToPct(getStepLossEstimate(step)?.estimatedLoss);
}

export function isStepOverThreshold(step: PlanStep, lossThreshold: number): boolean {
  return getStepLossPct(step) > fractionToPct(lossThreshold);
}

export function isStepDecided(step: PlanStep): boolean {
  return step.decision !== "pending";
}

/**
 * The choice shown in the radio group. A step at or under the threshold reads
 * as Accept by default, but that default is display-only: it is not persisted
 * until the engineer changes it.
 */
export function getStepChoice(
  step: PlanStep,
  lossThreshold: number
): DecisionChoice | undefined {
  const persisted = API_TO_DECISION[step.decision];
  if (persisted) return persisted;
  return isStepOverThreshold(step, lossThreshold) ? undefined : "accept";
}

function pickParam(params: Record<string, unknown>, keys: string[]): string | undefined {
  for (const key of keys) {
    const value = params[key];
    if (value === null || value === undefined || value === "") continue;
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }
  return undefined;
}

/**
 * Plain-language summary of a step, taken from the API when it provides one and
 * derived from the operation catalogue otherwise.
 */
export function describeStep(step: PlanStep): string {
  if (step.summary) return step.summary;

  const params = step.parameters ?? {};
  const column = pickParam(params, ["column", "sourceColumn", "columnName", "name"]);
  const target = pickParam(params, ["targetColumn", "newColumn", "to", "replacement"]);
  const from = pickParam(params, ["from", "oldValue", "search", "match"]);
  const type = pickParam(params, ["type", "toType", "castTo"]);
  const strategy = pickParam(params, ["strategy", "method", "fillWith"]);

  switch (step.operation) {
    case "replace_value":
      return from && target
        ? `Replace ${from} with ${target} in ${column ?? "the column"}`
        : `Replace values in ${column ?? "the column"}`;
    case "fill_missing":
      return strategy
        ? `Fill missing values in ${column ?? "the column"} using ${strategy}`
        : `Fill missing values in ${column ?? "the column"}`;
    case "drop_column":
      return `Drop the column ${column ?? "the column"}`;
    case "cast_type":
      return `Cast ${column ?? "the column"} to ${type ?? "its target type"}`;
    case "derive_column":
      return target && column
        ? `Derive ${target} from ${column}`
        : `Derive a new column from ${column ?? "the column"}`;
    case "expand_nested":
      return `Expand the nested structure in ${column ?? "the column"}`;
    case "deduplicate":
      return `Remove duplicate rows in ${column ?? "the column"}`;
    case "standardise_format":
      return `Standardise the format of ${column ?? "the column"}`;
    default:
      return String(step.operation).replace(/_/g, " ");
  }
}

type ServerStep = Partial<PlanStep> & { estimatedLoss?: LossEstimate | null };

function mergeStep(current: PlanStep, incoming: ServerStep): PlanStep {
  const { estimatedLoss, ...rest } = incoming;
  return {
    ...current,
    ...rest,
    lossEstimate: estimatedLoss ?? current.lossEstimate,
  };
}

// -----------------------------------------------------------------------------
// Errors
// -----------------------------------------------------------------------------

/**
 * Maps problem+json codes to the exact PRD copy (Backend CLAUDE.md error
 * catalogue); anything unmapped falls through to the backend message.
 */
export function mapPlanError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 400 && error.code === "REASON_REQUIRED") {
      return MSG_ENTER_REASON_MIN_10;
    }
    if (error.status === 409 && error.code === "PLAN_NOT_FULLY_DECIDED") {
      return MSG_DECIDE_EVERY_STEP;
    }
    return error.detail || error.title;
  }
  return MSG_DECIDE_EVERY_STEP;
}

// -----------------------------------------------------------------------------
// Queries
// -----------------------------------------------------------------------------

export function usePlan(planId: string | undefined): UseQueryResult<PlanDetail, ApiError> {
  return useQuery<PlanDetail, ApiError>({
    queryKey: planQueryKey(planId ?? ""),
    enabled: Boolean(planId),
    queryFn: ({ signal }) =>
      api.get(`plans/${planId}`, { signal }).json<PlanDetail>(),
  });
}

// -----------------------------------------------------------------------------
// Mutations
// -----------------------------------------------------------------------------

export interface DecideStepVariables {
  planId: string;
  stepId: string;
  decision: DecisionChoice;
  reason?: string;
  params?: EditParams;
}

export type UseDecideStepResult = UseMutationResult<
  PlanStep,
  ApiError,
  DecideStepVariables,
  { previous: PlanDetail | undefined }
>;

export function useDecideStep(): UseDecideStepResult {
  const queryClient = useQueryClient();

  return useMutation<PlanStep, ApiError, DecideStepVariables, { previous: PlanDetail | undefined }>({
    mutationFn: async ({ planId, stepId, decision, reason, params }) => {
      const body: Record<string, unknown> = { decision: toApiDecision(decision) };
      if (reason !== undefined) body.reason = reason;
      if (params !== undefined) body.parameters = params;

      return api
        .patch(`plans/${planId}/steps/${stepId}`, { json: body })
        .json<PlanStep>();
    },
    onMutate: async ({ planId, stepId, decision, reason, params }) => {
      const queryKey = planQueryKey(planId);
      await queryClient.cancelQueries({ queryKey });

      const previous = queryClient.getQueryData<PlanDetail>(queryKey);

      queryClient.setQueryData<PlanDetail>(queryKey, (current) => {
        if (!current) return current;
        return {
          ...current,
          steps: current.steps.map((step) =>
            step.id === stepId
              ? {
                  ...step,
                  decision: toApiDecision(decision) as StepDecision,
                  decisionReason: reason ?? null,
                  parameters: params ?? step.parameters,
                }
              : step
          ),
        };
      });

      return { previous };
    },
    onError: (_error, { planId }, context) => {
      if (context?.previous) {
        queryClient.setQueryData(planQueryKey(planId), context.previous);
      }
    },
    onSuccess: (serverStep, { planId, stepId }) => {
      queryClient.setQueryData<PlanDetail>(planQueryKey(planId), (current) => {
        if (!current) return current;
        return {
          ...current,
          steps: current.steps.map((step) =>
            step.id === stepId ? mergeStep(step, serverStep) : step
          ),
        };
      });
    },
    onSettled: (_data, _error, { planId }) => {
      void queryClient.invalidateQueries({ queryKey: planQueryKey(planId) });
    },
  });
}

export interface ApprovePlanVariables {
  planId: string;
  datasetId?: string;
}

export type UseApprovePlanResult = UseMutationResult<
  ApprovePlanResponse,
  ApiError,
  ApprovePlanVariables
>;

export function useApprovePlan(): UseApprovePlanResult {
  const queryClient = useQueryClient();

  return useMutation<ApprovePlanResponse, ApiError, ApprovePlanVariables>({
    mutationFn: ({ planId }) =>
      api.post(`plans/${planId}/approve`).json<ApprovePlanResponse>(),
    onSuccess: (_data, { planId, datasetId }) => {
      void queryClient.invalidateQueries({ queryKey: planQueryKey(planId) });
      void queryClient.invalidateQueries({ queryKey: ["plans"] });
      if (datasetId) {
        void queryClient.invalidateQueries({ queryKey: ["datasets", datasetId] });
      }
    },
  });
}

export interface RegeneratePlanVariables {
  datasetId: string;
  supersededPlanId?: string;
  lossThreshold?: number;
}

export type UseRegeneratePlanResult = UseMutationResult<
  PlanDetail,
  ApiError,
  RegeneratePlanVariables
>;

export function useRegeneratePlan(): UseRegeneratePlanResult {
  const queryClient = useQueryClient();

  return useMutation<PlanDetail, ApiError, RegeneratePlanVariables>({
    mutationFn: ({ datasetId, lossThreshold }) =>
      api
        .post(`datasets/${datasetId}/plans`, {
          json: lossThreshold === undefined ? {} : { lossThreshold },
        })
        .json<PlanDetail>(),
    onSuccess: (plan, { datasetId, supersededPlanId }) => {
      if (supersededPlanId) {
        queryClient.removeQueries({ queryKey: planQueryKey(supersededPlanId), exact: true });
      }
      queryClient.setQueryData(planQueryKey(plan.id), plan);
      void queryClient.invalidateQueries({ queryKey: ["plans"] });
      void queryClient.invalidateQueries({ queryKey: ["datasets", datasetId] });
      void queryClient.invalidateQueries({ queryKey: ["profile", datasetId] });
    },
  });
}
