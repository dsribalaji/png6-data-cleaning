import { z } from "zod";
import { MSG_ENTER_REASON_MIN_10 } from "../../shared/constants/messages";
import type { StepDecision } from "../../api/schema";

export const REASON_MIN_LENGTH = 10;
export const REASON_MAX_LENGTH = 500;

/**
 * Per-operation step parameters, edited as a JSON-friendly key/value form.
 * Deliberately generic: the operation catalogue owns the per-op rules, the
 * backend re-validates them (INVALID_PARAMETERS) when the decision is saved.
 */
export const editParamsSchema = z.record(z.string(), z.unknown());

export type EditParams = z.infer<typeof editParamsSchema>;

export const decisionChoiceSchema = z.enum(["accept", "edit", "reject"]);

export type DecisionChoice = z.infer<typeof decisionChoiceSchema>;

export const decisionSchema = z
  .object({
    decision: decisionChoiceSchema,
    reason: z
      .string()
      .min(REASON_MIN_LENGTH, MSG_ENTER_REASON_MIN_10)
      .max(REASON_MAX_LENGTH, MSG_ENTER_REASON_MIN_10)
      .optional(),
    params: editParamsSchema.optional(),
  })
  .refine(
    (value) => value.decision !== "reject" || Boolean(value.reason),
    { message: MSG_ENTER_REASON_MIN_10, path: ["reason"] }
  );

export type DecisionInput = z.infer<typeof decisionSchema>;

/**
 * The three choices the engineer makes, mapped onto the API decision vocabulary
 * (pending | accepted | edited | rejected).
 */
export const DECISION_TO_API: Record<DecisionChoice, Exclude<StepDecision, "pending">> = {
  accept: "accepted",
  edit: "edited",
  reject: "rejected",
};

export const API_TO_DECISION: Partial<Record<StepDecision, DecisionChoice>> = {
  accepted: "accept",
  edited: "edit",
  rejected: "reject",
};

export function toApiDecision(choice: DecisionChoice): Exclude<StepDecision, "pending"> {
  return DECISION_TO_API[choice];
}
