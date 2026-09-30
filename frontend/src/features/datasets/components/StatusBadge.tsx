import { Badge, type BadgeVariant } from "../../../shared/ui/Badge";
import type { DatasetStatus } from "../../../api/schema";

/**
 * CRMS pill mapping for dataset status (PRD Section 7, S3):
 * Profiling = info, Plan ready = warning, Approved/Executed = success,
 * Tests failed/Failed = danger, Rolled back = secondary.
 * `profiled` (profile complete, no plan yet) has no PRD colour of its own and
 * shares the info pill with Profiling.
 */
export const DATASET_STATUS_VARIANT: Record<DatasetStatus, BadgeVariant> = {
  profiling: "info",
  profiled: "info",
  plan_ready: "warning",
  approved: "success",
  executed: "success",
  tests_failed: "danger",
  failed: "danger",
  rolled_back: "secondary",
};

/** The label is always shown: colour is never the only signal (WCAG 2.1 AA). */
export const DATASET_STATUS_LABEL: Record<DatasetStatus, string> = {
  profiling: "Profiling",
  profiled: "Profiled",
  plan_ready: "Plan ready",
  approved: "Approved",
  executed: "Executed",
  tests_failed: "Tests failed",
  failed: "Failed",
  rolled_back: "Rolled back",
};

export const DATASET_STATUS_OPTIONS: DatasetStatus[] = [
  "profiling",
  "profiled",
  "plan_ready",
  "approved",
  "executed",
  "tests_failed",
  "rolled_back",
  "failed",
];

export interface StatusBadgeProps {
  status: DatasetStatus | undefined;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  if (!status) {
    return (
      <Badge variant="secondary" className={className}>
        Unknown
      </Badge>
    );
  }

  return (
    <Badge variant={DATASET_STATUS_VARIANT[status]} className={className}>
      {DATASET_STATUS_LABEL[status]}
    </Badge>
  );
}

export default StatusBadge;
