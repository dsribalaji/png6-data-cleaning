import { useMemo, useState } from "react";
import { MSG_AI_TAG, MSG_AI_TAG_TITLE } from "../../../shared/constants/messages";
import { IconBulb } from "@tabler/icons-react";
import type { InferredRule } from "../../../api/schema";
import { Badge } from "../../../shared/ui/Badge";
import { Button } from "../../../shared/ui/Button";
import { Card } from "../../../shared/ui/Card";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { Modal } from "../../../shared/ui/Modal";
import { Skeleton } from "../../../shared/ui/Skeleton";
import { MSG_CLOSE } from "../../../shared/constants/messages";

const EVIDENCE_LABEL = "Evidence";
const CONFIDENCE_LABEL = "Confidence";
const EVIDENCE_TITLE = "Evidence rows";
const EVIDENCE_DESCRIPTION = "Up to 10 sample rows that support this rule.";
const NO_EVIDENCE = "No evidence rows were returned for this rule.";
const NO_RULES = "No rules were inferred for this dataset.";
const MAX_EVIDENCE_ROWS = 10;
const MAX_EVIDENCE_COLUMNS = 8;

const RULE_TYPE_LABELS: Record<InferredRule["ruleType"], string> = {
  entity_group: "Entity group",
  arithmetic: "Arithmetic",
  primary_key: "Primary key",
  one_to_many: "One to many",
  semantic_type: "Semantic type",
  cross_field_fill: "Cross-field fill",
};

function expressionToText(expression: Record<string, unknown> | undefined): string {
  if (!expression) return "—";
  try {
    return JSON.stringify(expression);
  } catch {
    return "—";
  }
}

function cellText(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return "—";
    }
  }
  return String(value);
}

export interface EvidenceModalProps {
  isOpen: boolean;
  onClose: () => void;
  rows: Array<Record<string, unknown>>;
}

export function EvidenceModal({ isOpen, onClose, rows }: EvidenceModalProps) {
  const sample = useMemo(() => rows.slice(0, MAX_EVIDENCE_ROWS), [rows]);
  const headers = useMemo(() => {
    const found: string[] = [];
    for (const row of sample) {
      for (const key of Object.keys(row)) {
        if (!found.includes(key)) found.push(key);
        if (found.length >= MAX_EVIDENCE_COLUMNS) return found;
      }
    }
    return found;
  }, [sample]);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={EVIDENCE_TITLE}
      description={EVIDENCE_DESCRIPTION}
      maxWidth="xl"
      footer={
        <Button variant="secondary" onClick={onClose}>
          {MSG_CLOSE}
        </Button>
      }
    >
      {sample.length === 0 ? (
        <p className="text-sm text-[#6c757d] dark:text-[#a0aec0]">
          {NO_EVIDENCE}
        </p>
      ) : (
        <div className="max-h-[50vh] overflow-auto rounded-md border border-[#e9ecef] dark:border-[#343a40]">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="sticky top-0 bg-[#f8f9fa] dark:bg-[#1f2327] text-[#6c757d] dark:text-[#a0aec0]">
              <tr>
                {headers.map((header) => (
                  <th
                    key={header}
                    scope="col"
                    className="px-3 py-2.5 font-semibold uppercase tracking-wider"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e9ecef] dark:divide-[#343a40]">
              {sample.map((row, rowIndex) => (
                <tr key={`evidence-row-${rowIndex}`}>
                  {headers.map((header) => (
                    <td
                      key={header}
                      className="max-w-[18rem] truncate px-3 py-2 text-[#1f2937] dark:text-[#f3f4f6]"
                    >
                      {cellText(row[header])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
}

export interface InferredRulesListProps {
  rules: InferredRule[] | undefined;
  loading?: boolean;
}

/**
 * S4 inferred rules (PRD Section 7, wireframe 1e): expression, confidence at
 * two decimal places, and an Evidence button opening up to 10 sample rows.
 */
export function InferredRulesList({ rules, loading = false }: InferredRulesListProps) {
  const [evidence, setEvidence] = useState<InferredRule | null>(null);

  return (
    <Card
      title="Inferred rules"
      subtitle="Proposed by the model from the profile. Nothing is applied until a plan is approved."
      noPadding
    >
      {loading && !rules ? (
        <div className="space-y-3 p-5">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : (rules?.length ?? 0) === 0 ? (
        <div className="p-5">
          <EmptyState
            icon={<IconBulb className="h-6 w-6 stroke-[1.5]" aria-hidden="true" />}
            message={NO_RULES}
          />
        </div>
      ) : (
        <ul className="divide-y divide-[#e9ecef] dark:divide-[#343a40]">
          {rules?.map((rule) => (
            <li
              key={rule.id}
              className="flex flex-wrap items-start justify-between gap-3 px-5 py-4"
            >
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary">
                    {RULE_TYPE_LABELS[rule.ruleType] ?? rule.ruleType}
                  </Badge>
                  {rule.source === "llm" && (
                    <Badge variant="info" title={MSG_AI_TAG_TITLE}>
                      {MSG_AI_TAG}
                    </Badge>
                  )}
                  {rule.columns.length > 0 && (
                    <span className="text-xs text-[#6c757d] dark:text-[#a0aec0]">
                      {rule.columns.join(", ")}
                    </span>
                  )}
                </div>
                <p className="mt-1.5 break-words font-mono text-xs text-[#1f2937] dark:text-[#f3f4f6]">
                  {expressionToText(rule.expression)}
                </p>
              </div>

              <div className="flex items-center gap-4">
                <div className="text-right">
                  <span className="block text-[11px] font-semibold uppercase tracking-wider text-[#6c757d] dark:text-[#a0aec0]">
                    {CONFIDENCE_LABEL}
                  </span>
                  <span className="text-sm font-semibold tabular-nums text-[#1f2937] dark:text-[#f3f4f6]">
                    {Number(rule.confidence ?? 0).toFixed(2)}
                  </span>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setEvidence(rule)}
                >
                  {EVIDENCE_LABEL}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <EvidenceModal
        isOpen={evidence !== null}
        onClose={() => setEvidence(null)}
        rows={evidence?.evidenceRows ?? []}
      />
    </Card>
  );
}

export default InferredRulesList;
