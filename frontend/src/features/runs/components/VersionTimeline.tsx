import { useState } from "react";
import { IconHistory, IconRotateClockwise } from "@tabler/icons-react";
import { usePermission } from "../../../auth/permissions";
import { formatDateTime, formatInt } from "../../../shared/lib/format";
import {
  MESSAGES,
  MSG_ORIGINAL_IMMUTABLE,
} from "../../../shared/constants/messages";
import { Badge } from "../../../shared/ui/Badge";
import { Button } from "../../../shared/ui/Button";
import { Card } from "../../../shared/ui/Card";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { Skeleton } from "../../../shared/ui/Skeleton";
import { useToast } from "../../../shared/ui/Toast";
import { ORIGINAL_VERSION_NO, mapRollbackError, useRollback, type Version } from "../api";
import { RollbackModal } from "./RollbackModal";

const CURRENT_LABEL = "Current";
const ROWS_LABEL = "Rows";
const COLUMNS_LABEL = "Columns";
const NO_SHAPE = "—";
const NO_VERSIONS = "No versions have been recorded for this plan yet.";
const rollbackQueued = (n: number): string => `Roll back to v${n} was queued.`;

export interface UndoneStepRange {
  /** First step that will be undone. */
  first: number;
  /** Last step that will be undone. */
  last: number;
}

/**
 * Steps undone by restoring `target`. One version is produced per executed step
 * (v0 is the untouched original, v1 follows step 1), so restoring v{n} reverses
 * steps n+1 up to the current version. `versions` must be newest first, which is
 * what `useVersions` returns.
 */
export function undoneStepRange(
  versions: Version[],
  target: Version | null,
  stepCount: number
): UndoneStepRange {
  const current = versions.find((version) => version.isCurrent) ?? versions[0] ?? null;
  const currentNo = current?.n ?? 0;

  if (!target || target.n >= currentNo) {
    const only = Math.max(1, currentNo);
    return { first: only, last: only };
  }

  const index = versions.findIndex((version) => version.n === target.n);
  const newer = index > 0 ? versions[index - 1] : null;
  const first = Math.max(1, (newer?.n ?? target.n) + 1);
  const last =
    stepCount > 0 ? Math.min(currentNo, stepCount) : Math.max(currentNo, first);

  return { first: Math.min(first, last), last };
}

export interface VersionTimelineProps {
  planId: string;
  /** Newest first, as returned by `useVersions`. */
  versions: Version[];
  /** Plan step count; keeps the "steps a–b" copy inside the plan. */
  stepCount?: number;
  /** Dataset of the plan, so its row refreshes after a rollback. */
  datasetId?: string;
  loading?: boolean;
}

/**
 * S6 version timeline (PRD Section 7, wireframe 1i): newest first, v0 labelled
 * "Original (immutable)", and "Roll back here" on every row except the current
 * one — hidden (not disabled) for roles without `plan.rollback`.
 */
export function VersionTimeline({
  planId,
  versions,
  stepCount = 0,
  datasetId,
  loading = false,
}: VersionTimelineProps) {
  const canRollback = usePermission("plan.rollback");
  const toast = useToast();
  const rollback = useRollback();

  const [target, setTarget] = useState<Version | null>(null);
  const [rollbackError, setRollbackError] = useState<string | null>(null);

  const openModal = (version: Version) => {
    setRollbackError(null);
    setTarget(version);
  };

  const closeModal = () => {
    if (rollback.isPending) return;
    setTarget(null);
    setRollbackError(null);
  };

  const handleConfirm = async (reason: string) => {
    if (!target) return;
    try {
      await rollback.mutateAsync({ planId, version: target.n, reason, datasetId });
      setTarget(null);
      setRollbackError(null);
      toast.success(rollbackQueued(target.n));
    } catch (error: unknown) {
      // Kept inline in the modal: the reason stays editable after a 400.
      setRollbackError(mapRollbackError(error));
    }
  };

  const range = undoneStepRange(versions, target, stepCount);

  return (
    <Card
      title="Version timeline"
      subtitle="Every executed version is kept. Rolling back creates a new logged version, so nothing is lost."
      noPadding
    >
      {loading && versions.length === 0 ? (
        <div className="space-y-4 p-5" role="status" aria-label="Loading versions">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-3/4" />
        </div>
      ) : versions.length === 0 ? (
        <div className="p-5">
          <EmptyState
            icon={<IconHistory className="h-6 w-6 stroke-[1.5]" aria-hidden="true" />}
            message={NO_VERSIONS}
          />
        </div>
      ) : (
        <ol className="px-5 py-5">
          {versions.map((version, index) => {
            const isOriginal = version.n === ORIGINAL_VERSION_NO;
            const isLast = index === versions.length - 1;
            const rows = version.rows === null ? NO_SHAPE : formatInt(version.rows);
            const cols = version.cols === null ? NO_SHAPE : formatInt(version.cols);

            return (
              <li
                key={version.n}
                className="relative pl-8 pb-5 last:pb-0"
              >
                <span
                  className="absolute left-[3px] top-2 h-3.5 w-3.5 rounded-full border-2 border-white dark:border-[#24282e] bg-[#fd6321]"
                  aria-hidden="true"
                />
                {!isLast && (
                  <span
                    className="absolute left-[9px] top-7 bottom-0 w-px bg-[#e9ecef] dark:bg-[#343a40]"
                    aria-hidden="true"
                  />
                )}

                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-bold tabular-nums text-[#1f2937] dark:text-[#f3f4f6]">
                        v{version.n}
                      </span>
                      {version.isCurrent && (
                        <Badge variant="success">{CURRENT_LABEL}</Badge>
                      )}
                      {isOriginal ? (
                        <Badge variant="secondary">{MSG_ORIGINAL_IMMUTABLE}</Badge>
                      ) : version.label ? (
                        <span className="text-xs text-[#6c757d] dark:text-[#a0aec0]">
                          {version.label}
                        </span>
                      ) : null}
                    </div>

                    <p className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-0.5 text-xs text-[#6c757d] dark:text-[#a0aec0]">
                      <span>{formatDateTime(version.createdAt)}</span>
                      <span>
                        {ROWS_LABEL} {rows}
                      </span>
                      <span>
                        {COLUMNS_LABEL} {cols}
                      </span>
                    </p>
                  </div>

                  {!version.isCurrent && canRollback && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => openModal(version)}
                      leftIcon={
                        <IconRotateClockwise className="h-3.5 w-3.5" aria-hidden="true" />
                      }
                    >
                      {MESSAGES.ROLL_BACK_HERE}
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}

      <RollbackModal
        isOpen={target !== null}
        version={target}
        fromStep={range.first}
        toStep={range.last}
        submitting={rollback.isPending}
        error={rollbackError}
        onClose={closeModal}
        onConfirm={(reason) => void handleConfirm(reason)}
      />
    </Card>
  );
}

export default VersionTimeline;