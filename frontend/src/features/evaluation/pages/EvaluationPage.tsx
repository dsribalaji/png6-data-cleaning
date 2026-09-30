import { useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { IconFlask, IconPlayerPlay } from "@tabler/icons-react";
import { Can } from "../../../auth/Can";
import { ApiError } from "../../../api/client";
import type { EvaluationRun } from "../../../api/schema";
import { Badge } from "../../../shared/ui/Badge";
import { Button } from "../../../shared/ui/Button";
import { DataTable } from "../../../shared/ui/DataTable";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { Modal } from "../../../shared/ui/Modal";
import { Select } from "../../../shared/ui/Select";
import { useToast } from "../../../shared/ui/Toast";
import { formatDateTime, formatPct } from "../../../shared/lib/format";
import {
  MSG_BENCHMARK_SET,
  MSG_BENCHMARK_SETS_NOTE,
  MSG_CANCEL,
  MSG_DURATION,
  MSG_EVALUATION_DETAIL_TITLE,
  MSG_EVALUATION_STARTED,
  MSG_EVALUATION_SUBTITLE,
  MSG_EVALUATION_TITLE,
  MSG_EVALUATIONS_LOAD_FAILED,
  MSG_LOADING,
  MSG_MODEL,
  MSG_NOT_AVAILABLE,
  MSG_NO_EVALUATIONS,
  MSG_PASS_RATE,
  MSG_RUNNING,
  MSG_STARTED,
  MSG_START_EVALUATION,
  formatDuration,
} from "../../../shared/constants/messages";
import {
  BENCHMARK_SET_OPTIONS,
  DEFAULT_BENCHMARK_SET,
  isEvaluationRunning,
  startEvaluationErrorMessage,
  useEvaluation,
  useEvaluations,
  useStartEvaluation,
} from "../api";

/** Pass rate arrives as a fraction (0.95) and is shown as a percentage. */
function formatPassRate(passRate: number | undefined | null): string {
  if (passRate === undefined || passRate === null) return MSG_NOT_AVAILABLE;
  return formatPct(passRate * 100);
}

interface StartEvaluationModalProps {
  isOpen: boolean;
  onClose: () => void;
}

function StartEvaluationModal({ isOpen, onClose }: StartEvaluationModalProps) {
  const toast = useToast();
  const startMutation = useStartEvaluation();
  const [benchmarkSet, setBenchmarkSet] = useState<string>(DEFAULT_BENCHMARK_SET);
  const [error, setError] = useState<string | null>(null);

  const isPending = startMutation.isPending;

  const handleStart = () => {
    setError(null);
    startMutation.mutate(
      { benchmarkSet },
      {
        onSuccess: () => {
          toast.success(MSG_EVALUATION_STARTED);
          setBenchmarkSet(DEFAULT_BENCHMARK_SET);
          onClose();
        },
        onError: (mutationError) => {
          setError(startEvaluationErrorMessage(mutationError));
        },
      }
    );
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={isPending ? () => undefined : onClose}
      title={MSG_START_EVALUATION}
      maxWidth="sm"
      closeOnOverlayClick={!isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isPending}>
            {MSG_CANCEL}
          </Button>
          <Button
            onClick={handleStart}
            loading={isPending}
            leftIcon={<IconPlayerPlay className="h-4 w-4" aria-hidden="true" />}
          >
            {MSG_START_EVALUATION}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Select
          label={
            <>
              {MSG_BENCHMARK_SET}{" "}
              <span className="font-bold text-red-500" aria-hidden="true">
                *
              </span>
            </>
          }
          required
          value={benchmarkSet}
          disabled={isPending}
          onChange={(event) => setBenchmarkSet(event.target.value)}
          hint={MSG_BENCHMARK_SETS_NOTE}
          options={BENCHMARK_SET_OPTIONS.map((option) => ({
            value: option.value,
            label: option.label,
          }))}
        />

        {error && (
          <p
            role="alert"
            className="rounded-md border border-[#f5c6cb] bg-[#f8d7da] px-3 py-2 text-sm text-[#721c24] dark:border-[#662025] dark:bg-[#3d1a1c] dark:text-[#f5a3a9]"
          >
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}

interface RunDetailModalProps {
  runId: string | null;
  onClose: () => void;
}

/** Detail drawer for one run; polls itself while the run is still going. */
function RunDetailModal({ runId, onClose }: RunDetailModalProps) {
  const detailQuery = useEvaluation(runId);
  const run = detailQuery.data ?? null;
  const isRunning = isEvaluationRunning(run);

  return (
    <Modal
      isOpen={Boolean(runId)}
      onClose={onClose}
      title={MSG_EVALUATION_DETAIL_TITLE}
      description={run?.benchmarkSetName ?? run?.benchmarkSetId}
      maxWidth="md"
      footer={
        <Button variant="secondary" onClick={onClose}>
          {MSG_CANCEL}
        </Button>
      }
    >
      {detailQuery.isPending && (
        <p role="status" className="text-sm text-[#6c757d] dark:text-[#a0aec0]">
          {MSG_LOADING(MSG_EVALUATION_DETAIL_TITLE)}
        </p>
      )}

      {isRunning && (
        <div className="mb-3">
          <Badge variant="info">{MSG_RUNNING}</Badge>
        </div>
      )}

      {run && (
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <dt className="text-[#6c757d] dark:text-[#a0aec0]">{MSG_BENCHMARK_SET}</dt>
          <dd className="font-medium">
            {run.benchmarkSetName ?? run.benchmarkSetId}
          </dd>

          <dt className="text-[#6c757d] dark:text-[#a0aec0]">{MSG_MODEL}</dt>
          <dd className="font-medium">
            {run.modelName ?? MSG_NOT_AVAILABLE}
          </dd>

          <dt className="text-[#6c757d] dark:text-[#a0aec0]">{MSG_STARTED}</dt>
          <dd className="tabular-nums">{formatDateTime(run.startedAt)}</dd>

          <dt className="text-[#6c757d] dark:text-[#a0aec0]">{MSG_DURATION}</dt>
          <dd className="tabular-nums">
            {isRunning ? MSG_RUNNING : formatDuration(run.durationSeconds)}
          </dd>

          <dt className="text-[#6c757d] dark:text-[#a0aec0]">{MSG_PASS_RATE}</dt>
          <dd className="tabular-nums font-medium">
            {isRunning ? MSG_RUNNING : formatPassRate(run.passRate)}
          </dd>
        </dl>
      )}

      {detailQuery.isError && (
        <p
          role="alert"
          className="mt-3 rounded-md border border-[#f5c6cb] bg-[#f8d7da] px-3 py-2 text-sm text-[#721c24] dark:border-[#662025] dark:bg-[#3d1a1c] dark:text-[#f5a3a9]"
        >
          {detailQuery.error instanceof ApiError
            ? detailQuery.error.detail || detailQuery.error.title
            : MSG_EVALUATIONS_LOAD_FAILED}
        </p>
      )}
    </Modal>
  );
}

/**
 * S10 Evaluation (PRD Section 7, wireframe 1m).
 *
 * Read-only apart from starting a run. A running run is polled every two
 * seconds until it finishes, so the pass rate and duration appear on their own.
 */
export function EvaluationPage() {
  const [isStartOpen, setIsStartOpen] = useState(false);
  const [detailRunId, setDetailRunId] = useState<string | null>(null);

  const runsQuery = useEvaluations();
  const runs = runsQuery.data ?? [];
  const hasRunningRun = runs.some(isEvaluationRunning);

  const columns: ColumnDef<EvaluationRun, any>[] = [
    {
      id: "benchmarkSetId",
      header: MSG_BENCHMARK_SET,
      accessorFn: (row) => row.benchmarkSetName ?? row.benchmarkSetId,
      cell: ({ row }) => (
        <span className="font-mono text-xs">
          {row.original.benchmarkSetName ?? row.original.benchmarkSetId}
        </span>
      ),
    },
    {
      id: "modelName",
      header: MSG_MODEL,
      accessorFn: (row) => row.modelName ?? "",
      cell: ({ row }) =>
        row.original.modelName ? (
          row.original.modelName
        ) : (
          <span className="text-[#6c757d] dark:text-[#a0aec0]">{MSG_NOT_AVAILABLE}</span>
        ),
    },
    {
      id: "startedAt",
      header: MSG_STARTED,
      accessorFn: (row) => row.startedAt,
      cell: ({ row }) => (
        <span className="whitespace-nowrap tabular-nums">
          {formatDateTime(row.original.startedAt)}
        </span>
      ),
    },
    {
      id: "durationSeconds",
      header: MSG_DURATION,
      accessorFn: (row) => row.durationSeconds ?? -1,
      cell: ({ row }) => (
        <span className="tabular-nums">
          {isEvaluationRunning(row.original)
            ? MSG_RUNNING
            : formatDuration(row.original.durationSeconds)}
        </span>
      ),
    },
    {
      id: "passRate",
      header: MSG_PASS_RATE,
      accessorFn: (row) => row.passRate ?? -1,
      cell: ({ row }) => (
        <span className="tabular-nums font-medium">
          {isEvaluationRunning(row.original)
            ? MSG_RUNNING
            : formatPassRate(row.original.passRate)}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[#1f2937] dark:text-[#f3f4f6]">
            {MSG_EVALUATION_TITLE}
          </h1>
          <p className="mt-0.5 text-sm text-[#6c757d] dark:text-[#a0aec0]">
            {MSG_EVALUATION_SUBTITLE}
          </p>
        </div>
        <Can perm="evaluation.run">
          <Button
            leftIcon={<IconPlayerPlay className="h-4 w-4" aria-hidden="true" />}
            onClick={() => setIsStartOpen(true)}
          >
            {MSG_START_EVALUATION}
          </Button>
        </Can>
      </header>

      {runsQuery.isError && (
        <div
          role="alert"
          className="rounded-md border border-[#f5c6cb] bg-[#f8d7da] px-4 py-3 text-sm text-[#721c24] dark:border-[#662025] dark:bg-[#3d1a1c] dark:text-[#f5a3a9]"
        >
          {runsQuery.error?.detail ||
            runsQuery.error?.title ||
            MSG_EVALUATIONS_LOAD_FAILED}
        </div>
      )}

      {runs.length === 0 && !runsQuery.isPending && !runsQuery.isError ? (
        <EmptyState
          icon={<IconFlask className="h-6 w-6 stroke-[1.5]" aria-hidden="true" />}
          message={MSG_NO_EVALUATIONS}
        />
      ) : (
        <DataTable
          columns={columns}
          data={runs}
          loading={runsQuery.isPending}
          emptyMessage={MSG_NO_EVALUATIONS}
          onRowClick={(run) => setDetailRunId(run.id)}
        />
      )}

      {/* The list is re-read every few seconds while a run is in flight, so the
          table fills in without the user doing anything. */}
      {hasRunningRun && (
        <p role="status" className="text-xs text-[#6c757d] dark:text-[#a0aec0]">
          {MSG_RUNNING}
        </p>
      )}

      <StartEvaluationModal
        isOpen={isStartOpen}
        onClose={() => setIsStartOpen(false)}
      />

      <RunDetailModal runId={detailRunId} onClose={() => setDetailRunId(null)} />
    </div>
  );
}

export default EvaluationPage;
