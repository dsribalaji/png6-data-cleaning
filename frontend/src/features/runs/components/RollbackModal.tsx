import { useEffect, useId, useState } from "react";
import { z } from "zod";
import { cx } from "../../../shared/lib/format";
import {
  MESSAGES,
  MSG_ENTER_REASON_MIN_10,
  rollbackConfirm,
} from "../../../shared/constants/messages";
import { Button } from "../../../shared/ui/Button";
import { FormField } from "../../../shared/ui/FormField";
import { Modal } from "../../../shared/ui/Modal";
import type { Version } from "../api";

const REASON_LABEL = "Reason";

// Mirrors execution.rollbacks.reason CHECK (length between 10 and 500) in
// backend/CLAUDE.md; the API answers 400 REASON_REQUIRED without it.
export const ROLLBACK_REASON_MIN_LENGTH = 10;
export const ROLLBACK_REASON_MAX_LENGTH = 500;

export const rollbackReasonSchema = z
  .string()
  .min(ROLLBACK_REASON_MIN_LENGTH, MSG_ENTER_REASON_MIN_10)
  .max(ROLLBACK_REASON_MAX_LENGTH, MSG_ENTER_REASON_MIN_10);

export interface RollbackModalProps {
  isOpen: boolean;
  /** Version the engineer picked in the timeline; null while closed. */
  version: Version | null;
  /** First step number that will be undone (`a` in the confirm copy). */
  fromStep: number;
  /** Last step number that will be undone (`b` in the confirm copy). */
  toStep: number;
  submitting?: boolean;
  /** Server-side failure shown inline, under the field. */
  error?: string | null;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}

/**
 * S6 rollback modal (PRD Section 7, wireframe 1i, preview.html spec). The rollback is itself a
 * logged version, so the copy states that it can be re-applied, and the reason
 * is mandatory — it goes into the audit trail.
 */
export function RollbackModal({
  isOpen,
  version,
  fromStep,
  toStep,
  submitting = false,
  error = null,
  onClose,
  onConfirm,
}: RollbackModalProps) {
  const [reason, setReason] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const fieldId = useId();

  useEffect(() => {
    if (isOpen) {
      setReason("");
      setFieldError(null);
    }
  }, [isOpen, version?.n]);

  const handleConfirm = () => {
    const parsed = rollbackReasonSchema.safeParse(reason);
    if (!parsed.success) {
      setFieldError(MSG_ENTER_REASON_MIN_10);
      return;
    }
    setFieldError(null);
    onConfirm(parsed.data);
  };

  const shownError = fieldError ?? error ?? undefined;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={MESSAGES.ROLL_BACK}
      maxWidth="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            {MESSAGES.CANCEL}
          </Button>
          <Button variant="danger" onClick={handleConfirm} loading={submitting}>
            {MESSAGES.ROLL_BACK}
          </Button>
        </>
      }
    >
      <p className="text-sm text-ink">
        {rollbackConfirm(version?.n ?? 0, fromStep, toStep)}
      </p>

      <div className="mt-4">
        <FormField
          label={REASON_LABEL}
          htmlFor={fieldId}
          required
          error={shownError}
          hint={`${ROLLBACK_REASON_MIN_LENGTH}-${ROLLBACK_REASON_MAX_LENGTH} characters`}
        >
          <textarea
            id={fieldId}
            rows={4}
            value={reason}
            maxLength={ROLLBACK_REASON_MAX_LENGTH}
            disabled={submitting}
            onChange={(event) => {
              setReason(event.target.value);
              if (fieldError) setFieldError(null);
            }}
            aria-invalid={Boolean(shownError)}
            className={cx(
              "block w-full rounded-lg border text-sm transition-colors shadow-sm px-3.5 py-2 resize-y",
              "bg-surface text-ink",
              "placeholder:text-muted",
              shownError
                ? "border-danger focus:border-danger focus:ring-danger"
                : "border-line focus:border-primary focus:ring-primary",
              "focus:outline-none focus:ring-1",
              "disabled:cursor-not-allowed disabled:bg-canvas disabled:opacity-60"
            )}
          />
        </FormField>
        <p className="mt-2 text-right text-xs tabular-nums text-ink2">
          {reason.length}/{ROLLBACK_REASON_MAX_LENGTH}
        </p>
      </div>
    </Modal>
  );
}

export default RollbackModal;