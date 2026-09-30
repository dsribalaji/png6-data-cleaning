import { useEffect, useMemo, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import {
  IconAlertTriangle,
  IconArrowLeft,
  IconBraces,
  IconFileSpreadsheet,
  IconFileTypeCsv,
  IconPlayerPlay,
} from "@tabler/icons-react";
import { useDatasetEvents } from "../../../api/realtime";
import type { DatasetEvent, ExportFormat, JobStatus, PlanStep } from "../../../api/schema";
import { usePermission } from "../../../auth/permissions";
import { cx, formatInt } from "../../../shared/lib/format";
import { MSG_EXPORT_BLOCKED_TESTS_FAILED } from "../../../shared/constants/messages";
import { Badge, type BadgeVariant } from "../../../shared/ui/Badge";
import { Button } from "../../../shared/ui/Button";
import { Card } from "../../../shared/ui/Card";
import { DataTable } from "../../../shared/ui/DataTable";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { Skeleton } from "../../../shared/ui/Skeleton";
import { useToast } from "../../../shared/ui/Toast";
import { usePlan } from "../../plans/api";
import { useDataset } from "../../datasets/api";
import { StatusBadge } from "../../datasets/components/StatusBadge";
import {
  PLAN_KEY,
  VALIDATION_KEY,
  VERSIONS_KEY,
  mapExportError,
  useExport,
  useValidation,
  useVersions,
  type ReconRow,
} from "../api";
import { TestSummary } from "../components/TestSummary";
import { VersionTimeline } from "../components/VersionTimeline";

// PRD S6 copy. The strings the PRD fixes word-for-word come from messages.ts;
// these are the remaining section headers and column labels.
const PAGE_TITLE = "Run";
const BACK_LABEL = "Plan review";
const LIVE_LABEL = "Live";
const RECONNECTING_LABEL = "Reconnecting…";
const STEPS_TITLE = "Live progress";
const STEPS_SUBTITLE = "Progress is pushed by the server; no refresh is needed.";
const RESULTS_TITLE = "Results";
const CHECK_LABEL = "Check";
const SOURCE_LABEL = "Source";
const OUTPUT_LABEL = "Output";
const OK_LABEL = "OK";
const MATCHED_LABEL = "Matched";
const MISMATCH_LABEL = "Mismatch";
const RECONCILIATION_TITLE = "Reconciliation";
const RECONCILIATION_SUBTITLE =
  "Source totals compared with the cleaned output of this version.";
const NO_RECONCILIATIONS = "No reconciliation checks have been run for this version.";
const EXPORT_TITLE = "Export";
const EXPORT_SUBTITLE = "Exports are produced from the validated output.";
const XLSX_LABEL = "XLSX";
const CSV_LABEL = "CSV";
const PIPELINE_LABEL = "Pipeline (JSON)";
const TESTS_TITLE = "Tests";
const TESTS_SUBTITLE = "Click a tile to see the list of tests.";
const VERSION_LABEL = "Version";
const ROWS_LABEL = "Rows";
const COLUMNS_LABEL = "Columns";
const TESTS_PASSED_LABEL = "Tests passed";
const TESTS_FAILED_LABEL = "Tests failed";
const PLAN_UNAVAILABLE_TITLE = "Plan unavailable";
const PLAN_UNAVAILABLE_MESSAGE = "The plan could not be loaded.";
const VALIDATION_UNAVAILABLE = "The test results could not be loaded.";
const NO_VALUE = "—";
const EXPORT_DOWNLOADING = "The export is downloading.";

// -----------------------------------------------------------------------------
// Live progress
// -----------------------------------------------------------------------------

export interface StepProgress {
  status: JobStatus;
  progressPct: number;
}

const JOB_STATUS_LABEL: Record<JobStatus, string> = {
  queued: "Queued",
  running: "Running",
  succeeded: "Done",
  failed: "Failed",
};

const JOB_STATUS_VARIANT: Record<JobStatus, BadgeVariant> = {
  queued: "secondary",
  running: "info",
  succeeded: "success",
  failed: "danger",
};

const PROGRESS_BAR: Record<JobStatus, string> = {
  queued: "bg-[#adb5bd] dark:bg-[#4b5563]",
  running: "bg-[#fd6321]",
  succeeded: "bg-emerald-500 dark:bg-emerald-400",
  failed: "bg-rose-500 dark:bg-rose-400",
};

/** Events that can advance the step list (execute / validate / rollback jobs). */
const PROGRESS_EVENT_TYPES = [
  "JobStatusChanged",
  "job.status",
  "job.progress",
  "JobFailed",
  "job.failed",
  "ValidationCompleted",
  "validation.completed",
  "RollbackCompleted",
  "rollback.completed",
];

const ROLLBACK_EVENT_TYPES = ["RollbackCompleted", "rollback.completed"];

/** Job types that act on a plan; other dataset jobs are ignored on S6. */
const RUN_JOB_TYPES = ["execute", "execution", "validate", "validation", "rollback", "run"];

function toJobStatus(value: unknown): JobStatus {
  return value === "running" || value === "succeeded" || value === "failed" ? value : "queued";
}

function clampPct(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return 0;
  return Math.min(100, Math.max(0, Math.round(value)));
}

function eventStepNo(event: DatasetEvent): number | null {
  const wire = event as DatasetEvent & { stepNo?: number | null };
  return typeof wire.stepNo === "number" && Number.isFinite(wire.stepNo) ? wire.stepNo : null;
}

/**
 * The event contract carries one progress figure for the whole job and no job
 * type, so anything unknown is accepted and any `stepNo`/`jobType` the backend
 * does send is used in preference.
 */
function isRunEvent(event: DatasetEvent): boolean {
  const wire = event as DatasetEvent & { jobType?: string | null };
  if (!PROGRESS_EVENT_TYPES.includes(event.type)) return false;
  if (typeof wire.jobType !== "string" || wire.jobType === "") return true;
  return RUN_JOB_TYPES.includes(wire.jobType.toLowerCase());
}

/**
 * Maps one `JobStatusChanged` event onto every step of the plan.
 * A `stepNo` on the event is authoritative. Otherwise the single job figure is
 * spread evenly over the steps, so a step is done once the job has passed its
 * band; when the job failed, the step in flight is the one that failed.
 */
export function deriveRunProgress(
  event: DatasetEvent | null,
  steps: PlanStep[]
): StepProgress[] {
  const total = steps.length;
  const queued = (): StepProgress => ({ status: "queued", progressPct: 0 });

  if (!event || !isRunEvent(event) || total === 0) {
    return steps.map(queued);
  }

  const status = toJobStatus(event.status);
  const jobPct = clampPct(event.progressPct);
  const explicitStepNo = eventStepNo(event);

  if (explicitStepNo !== null) {
    return steps.map((step): StepProgress => {
      if (step.stepNo < explicitStepNo) return { status: "succeeded", progressPct: 100 };
      if (step.stepNo > explicitStepNo) return queued();
      return { status, progressPct: status === "succeeded" ? 100 : jobPct };
    });
  }

  if (status === "succeeded") {
    return steps.map((): StepProgress => ({ status: "succeeded", progressPct: 100 }));
  }

  const bandEnd = (index: number) => ((index + 1) / total) * 100;
  let failedIndex = -1;
  if (status === "failed") {
    failedIndex = steps.findIndex((_step, index) => jobPct < bandEnd(index));
    if (failedIndex === -1) failedIndex = total - 1;
  }

  return steps.map((_step, index): StepProgress => {
    if (index === failedIndex) return { status: "failed", progressPct: 0 };

    const start = (index / total) * 100;
    const end = bandEnd(index);

    if (jobPct >= end) return { status: "succeeded", progressPct: 100 };
    if (jobPct > start) {
      const span = end - start;
      const within = span > 0 ? Math.round(((jobPct - start) / span) * 100) : 0;
      return { status: "running", progressPct: clampPct(within) };
    }
    return queued();
  });
}

function StepProgressRow({
  step,
  progress,
  isPending,
}: {
  step: PlanStep;
  progress: StepProgress;
  isPending: boolean;
}) {
  const { status, progressPct } = progress;
  const label = JOB_STATUS_LABEL[status];

  return (
    <li className="px-5 py-3.5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="w-6 flex-shrink-0 text-xs font-semibold tabular-nums text-[#6c757d] dark:text-[#a0aec0]">
            {step.stepNo}
          </span>
          <span className="min-w-0 truncate text-sm font-medium text-[#1f2937] dark:text-[#f3f4f6]">
            {step.summary ?? step.operation.replace(/_/g, " ")}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs tabular-nums text-[#6c757d] dark:text-[#a0aec0]">
            {status === "queued" ? NO_VALUE : `${progressPct}%`}
          </span>
          <Badge variant={JOB_STATUS_VARIANT[status]}>{label}</Badge>
        </div>
      </div>

      <div
        role="progressbar"
        aria-label={`Step ${step.stepNo}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progressPct}
        className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-[#e9ecef] dark:bg-[#343a40]"
      >
        <div
          className={cx(
            "h-full rounded-full transition-all duration-300",
            PROGRESS_BAR[status],
            isPending && "animate-pulse"
          )}
          style={{ width: `${progressPct}%` }}
        />
      </div>
    </li>
  );
}

// -----------------------------------------------------------------------------
// Reconciliation grid
// -----------------------------------------------------------------------------

function cellText(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return NO_VALUE;
  return typeof value === "number" ? formatInt(value) : String(value);
}

const reconColumns: ColumnDef<ReconRow, any>[] = [
  {
    id: "checkName",
    header: CHECK_LABEL,
    cell: ({ row }) => (
      <span className="font-medium text-[#1f2937] dark:text-[#f3f4f6]">
        {row.original.checkName}
      </span>
    ),
  },
  {
    id: "sourceValue",
    header: SOURCE_LABEL,
    meta: { align: "right" },
    cell: ({ row }) => cellText(row.original.sourceValue),
  },
  {
    id: "outputValue",
    header: OUTPUT_LABEL,
    meta: { align: "right" },
    cell: ({ row }) => cellText(row.original.outputValue),
  },
  {
    id: "ok",
    header: OK_LABEL,
    cell: ({ row }) =>
      row.original.ok ? (
        <Badge variant="success">{MATCHED_LABEL}</Badge>
      ) : (
        <Badge variant="danger">{MISMATCH_LABEL}</Badge>
      ),
  },
];

const EXPORT_FORMATS: Array<{ format: ExportFormat; label: string; icon: ReactNode }> = [
  {
    format: "xlsx",
    label: XLSX_LABEL,
    icon: <IconFileSpreadsheet className="h-4 w-4" aria-hidden="true" />,
  },
  {
    format: "csv",
    label: CSV_LABEL,
    icon: <IconFileTypeCsv className="h-4 w-4" aria-hidden="true" />,
  },
  {
    format: "pipeline",
    label: PIPELINE_LABEL,
    icon: <IconBraces className="h-4 w-4" aria-hidden="true" />,
  },
];

// -----------------------------------------------------------------------------
// Page
// -----------------------------------------------------------------------------

/**
 * S6 Run, tests, versions, rollback (PRD Section 7, wireframe 1i).
 *
 * The SSE stream `GET /datasets/{id}/events` is opened on mount and closed on
 * unmount by `useDatasetEvents`; it invalidates the plan, validation and version
 * caches, so the results and the timeline refresh without a page reload.
 */
export function RunPage() {
  const { id: planId = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();

  const planQuery = usePlan(planId);
  const plan = planQuery.data;
  const datasetId = plan?.datasetId;

  const { lastEvent, isConnected } = useDatasetEvents(datasetId);
  const datasetQuery = useDataset(datasetId);
  const validationQuery = useValidation(planId);
  const versionsQuery = useVersions(planId);
  const exportMutation = useExport();

  const canExport = usePermission("export");

  const steps = useMemo(() => plan?.steps ?? [], [plan]);
  const progress = useMemo(() => {
    // Step i writes version v{i}; a step whose version exists is done even if the
    // live event was missed (SSE reconnecting, page opened after the run).
    const latest = Math.max(0, ...(versionsQuery.data ?? []).map((v) => v.n));
    return deriveRunProgress(lastEvent, steps).map((p, i): StepProgress =>
      p.status === "queued" && latest >= i + 1 ? { status: "succeeded", progressPct: 100 } : p
    );
  }, [lastEvent, steps, versionsQuery.data]);

  const validation = validationQuery.data;
  const versions = versionsQuery.data;
  const currentVersion = versions?.find((version) => version.isCurrent) ?? null;
  const isRunComplete =
    steps.length > 0 && progress.every((entry) => entry.status === "succeeded");

  // The screen refreshes when the rollback finishes. realtime.ts already
  // invalidates these keys, but it can only do so when the event names the plan,
  // so the page guarantees it from the route id.
  useEffect(() => {
    if (!lastEvent || !ROLLBACK_EVENT_TYPES.includes(lastEvent.type)) return;
    void queryClient.invalidateQueries({ queryKey: [VERSIONS_KEY, planId] });
    void queryClient.invalidateQueries({ queryKey: [VALIDATION_KEY, planId] });
    void queryClient.invalidateQueries({ queryKey: [PLAN_KEY, planId] });
  }, [lastEvent, planId, queryClient]);

  const handleExport = async (format: ExportFormat) => {
    try {
      await exportMutation.mutateAsync({
        planId,
        format,
        datasetName: datasetQuery.data?.name,
      });
      toast.success(EXPORT_DOWNLOADING);
    } catch (error: unknown) {
      toast.error(mapExportError(error));
    }
  };

  if (planQuery.isError) {
    return (
      <Card>
        <EmptyState
          title={PLAN_UNAVAILABLE_TITLE}
          message={planQuery.error?.detail || planQuery.error?.title || PLAN_UNAVAILABLE_MESSAGE}
        />
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Button
            variant="ghost"
            size="sm"
            leftIcon={<IconArrowLeft className="h-4 w-4" aria-hidden="true" />}
            onClick={() => navigate(`/plans/${planId}`)}
          >
            {BACK_LABEL}
          </Button>

          <h1 className="mt-1.5 flex flex-wrap items-center gap-3 text-xl font-bold tracking-tight text-[#1f2937] dark:text-[#f3f4f6]">
            {PAGE_TITLE}
            <StatusBadge status={datasetQuery.data?.status} />
          </h1>

          <p className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[#6c757d] dark:text-[#a0aec0]">
            <span>{datasetQuery.data?.name ?? NO_VALUE}</span>
            <span
              role="status"
              className="inline-flex items-center gap-1.5"
              aria-live="polite"
            >
              <span
                className={cx(
                  "h-1.5 w-1.5 rounded-full",
                  isConnected
                    ? "bg-emerald-500 dark:bg-emerald-400"
                    : "bg-amber-500 dark:bg-amber-400"
                )}
                aria-hidden="true"
              />
              {isConnected ? LIVE_LABEL : RECONNECTING_LABEL}
            </span>
          </p>
        </div>
      </header>

      {/* 1 — Live progress, then the results once every step is done. */}
      <Card
        title={STEPS_TITLE}
        subtitle={STEPS_SUBTITLE}
        noPadding
        headerAction={
          lastEvent?.message ? (
            <span className="max-w-[22rem] truncate text-xs text-[#6c757d] dark:text-[#a0aec0]">
              {lastEvent.message}
            </span>
          ) : null
        }
      >
        {planQuery.isPending ? (
          <div className="space-y-4 p-5" role="status" aria-label="Loading steps">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-3/4" />
          </div>
        ) : steps.length === 0 ? (
          <div className="p-5">
            <EmptyState
              icon={<IconPlayerPlay className="h-6 w-6 stroke-[1.5]" aria-hidden="true" />}
              message="This plan has no steps to run."
            />
          </div>
        ) : (
          <>
            <ul className="divide-y divide-[#e9ecef] dark:divide-[#343a40]">
              {steps.map((step, index) => (
                <StepProgressRow
                  key={step.id}
                  step={step}
                  progress={progress[index] ?? { status: "queued", progressPct: 0 }}
                  isPending={progress[index]?.status === "running"}
                />
              ))}
            </ul>

            {isRunComplete && (
              <div className="border-t border-[#e9ecef] dark:border-[#343a40] bg-[#f8f9fa] dark:bg-[#1f2327] px-5 py-4">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-[#6c757d] dark:text-[#a0aec0]">
                  {RESULTS_TITLE}
                </h3>
                <dl className="mt-2 flex flex-wrap items-center gap-x-8 gap-y-2 text-sm">
                  <div>
                    <dt className="inline text-[#6c757d] dark:text-[#a0aec0]">
                      {VERSION_LABEL}:{" "}
                    </dt>
                    <dd className="inline font-semibold tabular-nums text-[#1f2937] dark:text-[#f3f4f6]">
                      v{currentVersion?.n ?? 0}
                    </dd>
                  </div>
                  <div>
                    <dt className="inline text-[#6c757d] dark:text-[#a0aec0]">
                      {ROWS_LABEL}:{" "}
                    </dt>
                    <dd className="inline font-semibold tabular-nums text-[#1f2937] dark:text-[#f3f4f6]">
                      {formatInt(
                        currentVersion?.rows ?? datasetQuery.data?.rowCount ?? 0
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="inline text-[#6c757d] dark:text-[#a0aec0]">
                      {COLUMNS_LABEL}:{" "}
                    </dt>
                    <dd className="inline font-semibold tabular-nums text-[#1f2937] dark:text-[#f3f4f6]">
                      {formatInt(
                        currentVersion?.cols ?? datasetQuery.data?.columnCount ?? 0
                      )}
                    </dd>
                  </div>
                  {validation && (
                    <div>
                      <Badge variant={validation.latestPassed ? "success" : "danger"}>
                        {validation.latestPassed
                          ? TESTS_PASSED_LABEL
                          : TESTS_FAILED_LABEL}
                      </Badge>
                    </div>
                  )}
                </dl>
              </div>
            )}
          </>
        )}
      </Card>

      {/* 2 — Test tiles; clicking one expands its test list. */}
      <Card title={TESTS_TITLE} subtitle={TESTS_SUBTITLE}>
        <TestSummary validation={validation} loading={validationQuery.isPending} />
      </Card>

      {/* 3 — Reconciliation grid. */}
      <Card title={RECONCILIATION_TITLE} subtitle={RECONCILIATION_SUBTITLE} noPadding>
        <div className="p-4">
          <DataTable
            columns={reconColumns}
            data={validation?.reconciliation ?? []}
            pageSize={10}
            loading={validationQuery.isPending}
            emptyMessage={NO_RECONCILIATIONS}
          />
        </div>
      </Card>

      {/* 4 — Exports: hidden while any test failed, with the PRD banner instead. */}
      {canExport && (
        <Card title={EXPORT_TITLE} subtitle={EXPORT_SUBTITLE}>
          {validationQuery.isPending ? (
            <Skeleton className="h-9 w-full max-w-sm" />
          ) : validationQuery.isError ? (
            <div
              role="alert"
              className="flex items-start gap-3 rounded-md border border-[#f5c6cb] bg-[#f8d7da] px-4 py-3 text-sm text-[#721c24] dark:border-[#662025] dark:bg-[#3d1a1c] dark:text-[#f5a3a9]"
            >
              <IconAlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
              <span>
                {validationQuery.error?.detail ||
                  validationQuery.error?.title ||
                  VALIDATION_UNAVAILABLE}
              </span>
            </div>
          ) : validation?.latestPassed ? (
            <div className="flex flex-wrap gap-3">
              {EXPORT_FORMATS.map((entry) => (
                <Button
                  key={entry.format}
                  variant="secondary"
                  onClick={() => void handleExport(entry.format)}
                  loading={
                    exportMutation.isPending &&
                    exportMutation.variables?.format === entry.format
                  }
                  disabled={exportMutation.isPending}
                  leftIcon={entry.icon}
                >
                  {entry.label}
                </Button>
              ))}
            </div>
          ) : (
            /* One or more tests failed: the actions are hidden, not disabled
               (PRD Section 2), and the banner explains why. */
            <div
              role="status"
              className="flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200"
            >
              <IconAlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
              <span>{MSG_EXPORT_BLOCKED_TESTS_FAILED}</span>
            </div>
          )}
        </Card>
      )}

      {/* 5 — Version timeline with the rollback modal. */}
      <VersionTimeline
        planId={planId}
        versions={versions ?? []}
        stepCount={steps.length}
        datasetId={datasetId}
        loading={versionsQuery.isPending}
      />
    </div>
  );
}

export default RunPage;