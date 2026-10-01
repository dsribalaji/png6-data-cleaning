import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import {
  IconAlertTriangle,
  IconArrowLeft,
  IconBraces,
  IconColumns,
  IconDatabase,
  IconTable,
  IconTopologyStar3,
} from "@tabler/icons-react";
import { Can } from "../../../auth/Can";
import { useDatasetEvents } from "../../../api/realtime";
import type { DatasetSource } from "../../../api/schema";
import { Button } from "../../../shared/ui/Button";
import { Card } from "../../../shared/ui/Card";
import { KpiCard } from "../../../shared/ui/KpiCard";
import { Skeleton } from "../../../shared/ui/Skeleton";
import { useToast } from "../../../shared/ui/Toast";
import { formatDateTime, formatInt } from "../../../shared/lib/format";
import {
  MSG_GENERATE_PLAN_BTN,
  MSG_GENERATING_PLAN,
  MSG_RETRY,
  MSG_SOURCE,
  MSG_VIEW_ROWS,
  planGenerationFailed,
  quarantinedBanner,
} from "../../../shared/constants/messages";
import {
  useDataset,
  useGeneratePlan,
  useProfile,
  useRules,
} from "../api";
import { InferredRulesList } from "../components/InferredRulesList";
import { FlaggedCellsCard } from "../components/FlaggedCellsCard";
import { AiStatusBanner } from "../../../shared/ui/AiStatusBanner";
import { ProfileGrid } from "../components/ProfileGrid";
import { QuarantineDrawer } from "../components/QuarantineDrawer";
import { StatusBadge } from "../components/StatusBadge";
import { motion, useReducedMotion } from "motion/react";

const SOURCE_LABELS: Record<DatasetSource, string> = {
  upload: "Upload file",
  n8n_folder: "n8n folder",
};

const KPI_ROWS = "Rows";
const KPI_COLUMNS = "Columns";
const KPI_COLUMNS_WITH_NULLS = "Columns with nulls";
const KPI_NESTED_COLUMNS = "Nested columns";
const KPI_QUARANTINED = "Quarantined rows";
const FILE_LABEL = "File";
const INGESTED_LABEL = "Ingested";
const NONE = "None";
const LOAD_FAILED = "This dataset could not be loaded.";
const FAILED_FALLBACK = "The plan job did not report a reason.";

const PLAN_GENERATED_EVENTS = ["PlanGenerated", "plan.generated"];
const JOB_FAILED_EVENTS = ["JobFailed", "job.failed"];

function isPlanGenerated(type: string, status = ""): boolean {
  // The backend's job.status stream reports type "plan" with status "completed".
  return PLAN_GENERATED_EVENTS.includes(type) || (type === "plan" && status === "completed");
}

/** A failed plan job arrives either as a dedicated event or as status "failed". */
function isJobFailed(type: string, status: string): boolean {
  return JOB_FAILED_EVENTS.includes(type) || status === "failed";
}

/**
 * messages.ts stores the whole banner in one string, trailing "View rows"
 * included. The sentence is split there so the link is a real button.
 */
function splitQuarantineBanner(count: number): { sentence: string; link: string } {
  const full = quarantinedBanner(count);
  const at = full.lastIndexOf(MSG_VIEW_ROWS);
  if (at === -1) {
    return { sentence: full, link: MSG_VIEW_ROWS };
  }
  return {
    sentence: full.slice(0, at).trimEnd(),
    link: full.slice(at).trim(),
  };
}

/**
 * S4 Dataset profile (PRD Section 7, wireframe 1e).
 * Subscribes to GET /datasets/{id}/events on mount and closes it on unmount.
 * The stream only patches query caches (or, here, the plan-generation state);
 * the page keeps no independent copy of server data.
 */
export function DatasetProfilePage() {
  const shouldReduceMotion = useReducedMotion();
  const { id } = useParams<{ id: string }>();
  const datasetId = id ?? "";
  const navigate = useNavigate();
  const toast = useToast();

  const datasetQuery = useDataset(datasetId);
  const profileQuery = useProfile(datasetId);
  const rulesQuery = useRules(datasetId);
  const planMutation = useGeneratePlan();
  const { lastEvent } = useDatasetEvents(datasetId);

  const [isQuarantineOpen, setIsQuarantineOpen] = useState(false);
  const [isAwaitingPlanEvent, setIsAwaitingPlanEvent] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const planIdFromResponse = useRef<string | null>(null);

  const dataset = datasetQuery.data;
  const summary = profileQuery.data?.summary;
  const isGenerating = planMutation.isPending || isAwaitingPlanEvent;

  // Plan navigation + failure toast are driven by the dataset SSE stream
  // (useDatasetEvents), which invalidates the dataset/profile/rules/
  // quarantine query keys via src/api/realtime.ts.
  useEffect(() => {
    if (!lastEvent) return;
    const type = lastEvent.type ?? "";
    const status = lastEvent.status ?? "";

    if (isPlanGenerated(type, status)) {
      const planId = lastEvent.planId ?? planIdFromResponse.current;
      setIsAwaitingPlanEvent(false);
      if (planId) {
        navigate(`/plans/${planId}`);
      }
      return;
    }

    if (isAwaitingPlanEvent && isJobFailed(type, status)) {
      setIsAwaitingPlanEvent(false);
      const message = lastEvent.message || FAILED_FALLBACK;
      setPlanError(planGenerationFailed(message));
      toast.error(planGenerationFailed(message));
    }
  }, [lastEvent, isAwaitingPlanEvent, navigate, toast]);

  const startPlanGeneration = async () => {
    setPlanError(null);
    setIsAwaitingPlanEvent(true);
    try {
      const response = await planMutation.mutateAsync({ id: datasetId });
      planIdFromResponse.current = response.planId ?? null;
      // Plan already generated (steps in the response): no need to wait for the event.
      if (response.planId && (response as { stepCount?: number }).stepCount) {
        setIsAwaitingPlanEvent(false);
        navigate(`/plans/${response.planId}`);
      }
    } catch (error) {
      setIsAwaitingPlanEvent(false);
      const message =
        error instanceof Error && error.message ? error.message : FAILED_FALLBACK;
      setPlanError(planGenerationFailed(message));
      toast.error(planGenerationFailed(message));
    }
  };

  const quarantinedRows =
    summary?.quarantinedRowsCount ?? dataset?.quarantineCount ?? 0;
  const banner = useMemo(
    () => splitQuarantineBanner(quarantinedRows),
    [quarantinedRows]
  );

  const isError = datasetQuery.isError || profileQuery.isError;

  if (isError) {
    return (
      <div
        role="alert"
        className="rounded-[10px] border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger dark:border-[#662025] dark:bg-[#3d1a1c] dark:text-[#f5a3a9]"
      >
        {LOAD_FAILED}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Button
            variant="ghost"
            size="sm"
            leftIcon={<IconArrowLeft className="h-4 w-4" aria-hidden="true" />}
            onClick={() => navigate("/datasets")}
          >
            Datasets
          </Button>
          <h1 className="mt-1.5 flex flex-wrap items-center gap-3 text-xl font-bold tracking-tight text-ink dark:text-[#f3f4f6]">
            {dataset?.name ?? "…"}
            <StatusBadge status={dataset?.status} />
          </h1>
          {dataset && (
            <p className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink2 dark:text-[#a0aec0]">
              <span>
                {MSG_SOURCE}: {SOURCE_LABELS[dataset.source] ?? dataset.source}
              </span>
              <span>
                {FILE_LABEL}: {dataset.fileName}
              </span>
              <span>
                {INGESTED_LABEL} {formatDateTime(dataset.ingestedAt)}
              </span>
            </p>
          )}
        </div>

        <Can perm="plan.generate">
          <Button
            onClick={startPlanGeneration}
            loading={isGenerating}
            leftIcon={<IconBraces className="h-4 w-4" aria-hidden="true" />}
          >
            {isGenerating ? MSG_GENERATING_PLAN : MSG_GENERATE_PLAN_BTN}
          </Button>
        </Can>
      </header>

      {planError && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger dark:border-[#662025] dark:bg-[#3d1a1c] dark:text-[#f5a3a9]"
        >
          <span>{planError}</span>
          {/* The shared Toast exposes no action slot, so the Retry action sits
              beside the message and survives the toast auto-dismiss. */}
          <Button
            variant="secondary"
            size="sm"
            onClick={startPlanGeneration}
            leftIcon={<IconAlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />}
          >
            {MSG_RETRY}
          </Button>
        </div>
      )}

      {quarantinedRows > 0 && (
        <div
          role="status"
          className="flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-ink dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200"
        >
          <span>{banner.sentence}</span>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsQuarantineOpen(true)}
          >
            {banner.link}
          </Button>
        </div>
      )}

      {datasetQuery.isPending || profileQuery.isPending ? (
        <div
          className="grid grid-cols-2 gap-4 lg:grid-cols-5"
          role="status"
          aria-label="Loading dataset summary"
        >
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={`kpi-skeleton-${index}`} className="h-24 rounded-lg" />
          ))}
        </div>
      ) : (
        <section
          aria-label="Dataset summary"
          className="grid grid-cols-2 gap-4 lg:grid-cols-5"
        >
          <motion.div
            initial={shouldReduceMotion ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={
              shouldReduceMotion
                ? { duration: 0 }
                : { duration: 0.22, ease: "easeOut", delay: 0 }
            }
          >
            <KpiCard
              label={KPI_ROWS}
              value={formatInt(summary?.rowCount ?? dataset?.rowCount ?? 0)}
              iconBgColor="bg-primary/10 text-primary"
              icon={<IconDatabase className="h-5 w-5" aria-hidden="true" />}
            />
          </motion.div>
          <motion.div
            initial={shouldReduceMotion ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={
              shouldReduceMotion
                ? { duration: 0 }
                : { duration: 0.22, ease: "easeOut", delay: 0.04 }
            }
          >
            <KpiCard
              label={KPI_COLUMNS}
              value={formatInt(summary?.columnCount ?? dataset?.columnCount ?? 0)}
              iconBgColor="bg-primary/10 text-primary"
              icon={<IconColumns className="h-5 w-5" aria-hidden="true" />}
            />
          </motion.div>
          <motion.div
            initial={shouldReduceMotion ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={
              shouldReduceMotion
                ? { duration: 0 }
                : { duration: 0.22, ease: "easeOut", delay: 0.08 }
            }
          >
            <KpiCard
              label={KPI_COLUMNS_WITH_NULLS}
              value={formatInt(summary?.columnsWithNullsCount ?? 0)}
              iconBgColor="bg-primary/10 text-primary"
              icon={<IconTable className="h-5 w-5" aria-hidden="true" />}
            />
          </motion.div>
          <motion.div
            initial={shouldReduceMotion ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={
              shouldReduceMotion
                ? { duration: 0 }
                : { duration: 0.22, ease: "easeOut", delay: 0.12 }
            }
          >
            <KpiCard
              label={KPI_NESTED_COLUMNS}
              value={formatInt(summary?.nestedColumnsCount ?? 0)}
              iconBgColor="bg-primary/10 text-primary"
              icon={<IconTopologyStar3 className="h-5 w-5" aria-hidden="true" />}
            />
          </motion.div>
          <motion.div
            initial={shouldReduceMotion ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={
              shouldReduceMotion
                ? { duration: 0 }
                : { duration: 0.22, ease: "easeOut", delay: 0.16 }
            }
          >
            <KpiCard
              label={KPI_QUARANTINED}
              value={formatInt(quarantinedRows)}
              subtext={quarantinedRows > 0 ? undefined : NONE}
              iconBgColor="bg-warning/10 text-warning"
              icon={<IconAlertTriangle className="h-5 w-5" aria-hidden="true" />}
            />
          </motion.div>
        </section>
      )}

      <Card
        title="Column profile"
        subtitle="Click a row to see the minimum, maximum and mean."
        noPadding
      >
        <div className="p-4">
          <ProfileGrid
            columns={profileQuery.data?.columns ?? []}
            loading={profileQuery.isFetching && !profileQuery.isPending}
          />
        </div>
      </Card>

      <AiStatusBanner
        status={profileQuery.data?.aiStatus}
        message={profileQuery.data?.aiMessage}
      />

      <InferredRulesList
        rules={rulesQuery.data}
        loading={rulesQuery.isPending || rulesQuery.isFetching}
      />

      <FlaggedCellsCard cells={profileQuery.data?.flaggedCells} />

      <QuarantineDrawer
        isOpen={isQuarantineOpen}
        onClose={() => setIsQuarantineOpen(false)}
        datasetId={datasetId}
        quarantinedRows={quarantinedRows}
      />
    </div>
  );
}

export default DatasetProfilePage;
