import { MESSAGES, approveConfirm } from "../../../shared/constants/messages";
import { Button } from "../../../shared/ui/Button";
import { Modal } from "../../../shared/ui/Modal";

export interface ApproveConfirmModalProps {
  isOpen: boolean;
  stepCount: number;
  submitting?: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

/**
 * Final gate before a plan is approved. Approving queues test generation and
 * execution, so the step count is spelled out before it is committed.
 */
export function ApproveConfirmModal({
  isOpen,
  stepCount,
  submitting = false,
  onClose,
  onConfirm,
}: ApproveConfirmModalProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={MESSAGES.APPROVE_PLAN}
      maxWidth="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            {MESSAGES.CANCEL}
          </Button>
          <Button onClick={onConfirm} loading={submitting}>
            {MESSAGES.CONFIRM}
          </Button>
        </>
      }
    >
      <p className="text-sm text-[#1f2937] dark:text-[#f3f4f6]">{approveConfirm(stepCount)}</p>
    </Modal>
  );
}
