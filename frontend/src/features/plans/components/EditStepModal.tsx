import { useEffect, useId, useState } from "react";
import type { PlanStep } from "../../../api/schema";
import { cx } from "../../../shared/lib/format";
import { MESSAGES } from "../../../shared/constants/messages";
import { Button } from "../../../shared/ui/Button";
import { Modal } from "../../../shared/ui/Modal";
import { Input } from "../../../shared/ui/Input";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { editParamsSchema, type EditParams } from "../schemas";

export interface EditStepModalProps {
  isOpen: boolean;
  step: PlanStep | null;
  submitting?: boolean;
  onClose: () => void;
  onConfirm: (params: EditParams) => void;
}

function toEditableText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function parseParamText(original: unknown, text: string): unknown {
  if (original === null || original === undefined) return text;
  if (typeof original === "number") {
    const parsed = Number(text.trim());
    return text.trim() !== "" && Number.isFinite(parsed) ? parsed : text;
  }
  if (typeof original === "boolean") {
    return text.trim().toLowerCase() === "true";
  }
  if (typeof original === "object") {
    try {
      return JSON.parse(text) as unknown;
    } catch {
      return text;
    }
  }
  return text;
}

/**
 * Edit the parameters of one step. The per-operation rules live in the backend
 * operation catalogue, so this is deliberately a generic JSON-friendly key/value
 * form: values keep the type they already had where it can be parsed back, and
 * anything unparseable is sent as plain text for the backend to reject with
 * INVALID_PARAMETERS rather than losing the engineer's edit.
 */
export function EditStepModal({
  isOpen,
  step,
  submitting = false,
  onClose,
  onConfirm,
}: EditStepModalProps) {
  const [draft, setDraft] = useState<Record<string, string>>({});
  const fieldPrefix = useId();

  const parameters = step?.parameters ?? {};
  const keys = Object.keys(parameters);

  useEffect(() => {
    if (!isOpen || !step) {
      setDraft({});
      return;
    }
    const initial: Record<string, string> = {};
    for (const [key, value] of Object.entries(step.parameters ?? {})) {
      initial[key] = toEditableText(value);
    }
    setDraft(initial);
  }, [isOpen, step?.id]);

  const handleSave = () => {
    if (!step) return;

    const next: EditParams = {};
    for (const [key, original] of Object.entries(step.parameters ?? {})) {
      next[key] = parseParamText(original, draft[key] ?? "");
    }

    const result = editParamsSchema.safeParse(next);
    if (!result.success) return;

    onConfirm(result.data);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={MESSAGES.EDIT}
      description={step ? `Step ${step.stepNo}` : undefined}
      maxWidth="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            {MESSAGES.CANCEL}
          </Button>
          <Button onClick={handleSave} loading={submitting} disabled={keys.length === 0}>
            {MESSAGES.SAVE}
          </Button>
        </>
      }
    >
      {keys.length === 0 ? (
        <EmptyState message="This step has no parameters to edit." />
      ) : (
        <div className="space-y-4 text-ink">
          {keys.map((key) => {
            const fieldId = `${fieldPrefix}-${key}`;
            return (
              <Input
                key={key}
                id={fieldId}
                label={key}
                value={draft[key] ?? ""}
                disabled={submitting}
                onChange={(event) =>
                  setDraft((prev) => ({ ...prev, [key]: event.target.value }))
                }
                className={cx("font-mono text-xs")}
              />
            );
          })}
        </div>
      )}
    </Modal>
  );
}

export default EditStepModal;
