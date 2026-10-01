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
            "block w-full rounded-lg border text-sm transition-colors shadow-sm px-3.5 py-2 resize-y",
            "bg-surface text-ink",
            "placeholder:text-muted",
            error
              ? "border-danger focus:border-danger focus:ring-danger"
              : "border-line focus:border-primary focus:ring-primary",
            "focus:outline-none focus:ring-1",
            "disabled:cursor-not-allowed disabled:bg-canvas disabled:opacity-60"
          )}
        />
      </FormField>
      <p className="mt-2 text-right text-xs tabular-nums text-ink2">
        {reason.length}/{REASON_MAX_LENGTH}
      </p>
    </Modal>
  );
}

export default RejectReasonModal;
