import { useEffect, useId, useState } from "react";
import type { PlanStep } from "../../../api/schema";
import { cx } from "../../../shared/lib/format";
import {
  MESSAGES,
  MSG_ENTER_REASON_MIN_10,
} from "../../../shared/constants/messages";
import { Button } from "../../../shared/ui/Button";
import { Modal } from "../../../shared/ui/Modal";
import { FormField } from "../../../shared/ui/FormField";
import {
  REASON_MAX_LENGTH,
  REASON_MIN_LENGTH,
  decisionSchema,
} from "../schemas";

export interface RejectReasonModalProps {
  isOpen: boolean;
  step: PlanStep | null;
  submitting?: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}

/**
 * Reject a proposed step. The reason is 10-500 characters and is required: it is
 * written to the audit trail, so the backend answers REASON_REQUIRED (400)
 * without it.
 */
export function RejectReasonModal({
  isOpen,
  step,
  submitting = false,
  onClose,
  onConfirm,
}: RejectReasonModalProps) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const fieldId = useId();

  useEffect(() => {
    if (isOpen) {
      setReason("");
      setError(null);
    }
  }, [isOpen, step?.id]);

  const handleConfirm = () => {
    const result = decisionSchema.safeParse({ decision: "reject", reason });
    if (!result.success) {
      setError(MSG_ENTER_REASON_MIN_10);
      return;
    }
    setError(null);
    onConfirm(result.data.reason ?? "");
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={MESSAGES.REJECT}
      description={step ? `Step ${step.stepNo}` : undefined}
      maxWidth="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            {MESSAGES.CANCEL}
          </Button>
          <Button variant="danger" onClick={handleConfirm} loading={submitting}>
            {MESSAGES.REJECT}
          </Button>
        </>
      }
    >
      <FormField
        label="Reason"
        htmlFor={fieldId}
        required
        error={error ?? undefined}
        hint={`${REASON_MIN_LENGTH}-${REASON_MAX_LENGTH} characters`}
      >
        <textarea
          id={fieldId}
          rows={4}
          value={reason}
          maxLength={REASON_MAX_LENGTH}
          disabled={submitting}
          onChange={(event) => {
            setReason(event.target.value);
            if (error) setError(null);
          }}
          aria-invalid={Boolean(error)}
          className={cx(
            "block w-full rounded-md border text-sm transition-colors shadow-sm px-3.5 py-2 resize-y",
            "bg-white dark:bg-[#1a1d21] text-[#1f2937] dark:text-[#f3f4f6]",
            "placeholder:text-[#adb5bd] dark:placeholder:text-[#6c757d]",
            error
              ? "border-rose-500 dark:border-rose-500 focus:border-rose-500 focus:ring-rose-500"
              : "border-[#d1d5db] dark:border-[#374151] focus:border-[#fd6321] focus:ring-[#fd6321]",
            "focus:outline-none focus:ring-1",
            "disabled:cursor-not-allowed disabled:bg-[#f8f9fa] dark:disabled:bg-[#2d3239] disabled:opacity-60"
          )}
        />
      </FormField>
      <p className="mt-2 text-right text-xs tabular-nums text-[#6c757d] dark:text-[#a0aec0]">
        {reason.length}/{REASON_MAX_LENGTH}
      </p>
    </Modal>
  );
}
