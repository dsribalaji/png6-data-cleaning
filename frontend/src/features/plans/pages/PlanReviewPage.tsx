import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { IconAlertTriangle, IconRefresh, IconCircleCheck } from "@tabler/icons-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { PlanStep } from "../../../api/schema";
import { Can } from "../../../auth/Can";
import { usePermission } from "../../../auth/permissions";
import {
  MESSAGES,
  MSG_PLAN_CONFIDENCE,
  MSG_PLAN_REPLACE_CONFIRM,
  approvePlanLabel,
  stepExceedsThreshold,
} from "../../../shared/constants/messages";
import { AiStatusBanner } from "../../../shared/ui/AiStatusBanner";
import { Button } from "../../../shared/ui/Button";
import { Card } from "../../../shared/ui/Card";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { Modal } from "../../../shared/ui/Modal";
import { Skeleton } from "../../../shared/ui/Skeleton";
import { useToast } from "../../../shared/ui/Toast";
import { cx } from "../../../shared/lib/format";
import {
  formatPct2dp,
  fractionToPct,
  isStepDecided,
  isStepOverThreshold,
  mapPlanError,
  useApprovePlan,
  useDecideStep,
  usePlan,
  useRegeneratePlan,
} from "../api";
import type { DecisionChoice, EditParams } from "../schemas";
import { ApproveConfirmModal } from "../components/ApproveConfirmModal";
import { EditStepModal } from "../components/EditStepModal";
import { RejectReasonModal } from "../components/RejectReasonModal";
import { StepDiffDrawer } from "../components/StepDiffDrawer";
import { StepTable, isNeverAutoStep } from "../components/StepTable";

export function PlanReviewPage() {
  const { id = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const shouldReduceMotion = useReducedMotion();

  const canDecide = usePermission("plan.decide");

  const { data: plan, isLoading, isError, error } = usePlan(id);
  const decideStep = useDecideStep();
  const approvePlan = useApprovePlan();
  const regeneratePlan = useRegeneratePlan();

  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [editStep, setEditStep] = useState<PlanStep | null>(null);
  const [rejectStep, setRejectStep] = useState<PlanStep | null>(null);
  const [isApproveOpen, setIsApproveOpen] = useState(false);
  const [isRegenerateOpen, setIsRegenerateOpen] = useState(false);

  const steps = useMemo(() => plan?.steps ?? [], [plan]);

  const lossThreshold = plan?.lossThreshold ?? 0;
  const decidedCount = steps.filter(isStepDecided).length;
  const allDecided = steps.length > 0 && decidedCount === steps.length;

  const overThresholdStep = steps.find(
    (step) => isStepOverThreshold(step, lossThreshold) && !isStepDecided(step)
  );

  const selectedStep =
    steps.find((step) => step.id === selectedStepId) ?? null;

  const pendingStepIds = decideStep.isPending && decideStep.variables?.stepId
    ? [decideStep.variables.stepId]
    : [];

  const runDecision = async (
    step: PlanStep,
    decision: DecisionChoice,
    extra?: { reason?: string; params?: EditParams }
  ) => {
    if (!plan) return;
    try {
      await decideStep.mutateAsync({
        planId: plan.id,
        stepId: step.id,
        decision,
        reason: extra?.reason,
        params: extra?.params,
      });
    } catch (err: unknown) {
      toast.error(mapPlanError(err));
    }
  };

  const handleDecisionChoice = (step: PlanStep, choice: DecisionChoice) => {
    if (choice === "accept") {
      void runDecision(step, "accept");
      return;
    }
    if (choice === "edit") {
      setEditStep(step);
      return;
    }
    setRejectStep(step);
  };

  const handleApproveAll = async () => {
    if (!plan || !canDecide) return;
    const pendingSteps = steps.filter((step) => !isStepDecided(step));
    const neverAutoSteps = pendingSteps.filter(isNeverAutoStep);
    const autoApprovable = pendingSteps.filter((step) => !isNeverAutoStep(step));

    for (const step of autoApprovable) {
      await runDecision(step, "accept");
    }

    if (neverAutoSteps.length > 0) {
      const names = neverAutoSteps.map((s) => `Step ${s.stepNo}`).join(", ");
      toast.info(`${names} requires individual approval — never auto-approved`);
    } else if (autoApprovable.length > 0) {
      toast.success("All pending steps approved");
    }
  };

  const handleRejectPlan = () => {
    toast.info("Plan marked for revision");
  };

  const handleApprove = async () => {
    if (!plan) return;
    try {
      await approvePlan.mutateAsync({ planId: plan.id, datasetId: plan.datasetId });
      setIsApproveOpen(false);
      navigate(`/plans/${plan.id}/run`);
    } catch (err: unknown) {
      toast.error(mapPlanError(err));
    }
  };

  const handleRegenerate = async () => {
    if (!plan) return;
    try {
      const nextPlan = await regeneratePlan.mutateAsync({
        datasetId: plan.datasetId,
        supersededPlanId: plan.id,
        lossThreshold: plan.lossThreshold,
      });
      setIsRegenerateOpen(false);
      setSelectedStepId(null);
      setEditStep(null);
      setRejectStep(null);
      navigate(`/plans/${nextPlan.id}`);
    } catch (err: unknown) {
      toast.error(mapPlanError(err));
    }
  };

  const totalLossPct = plan ? fractionToPct(plan.totalEstimatedLoss) : 0;
  const thresholdPct = fractionToPct(lossThreshold);
  const isTotalOverThreshold = thresholdPct > 0 && totalLossPct > thresholdPct;
  const totalBarWidth =
    thresholdPct > 0 ? Math.min(100, Math.round((totalLossPct / thresholdPct) * 100)) : 0;

  return (
    <div className="space-y-5">
      {/* Topbar navigation link to diagnosis if available */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-ink">
            Plan review
          </h1>
          {plan ? (
            <p className="mt-1 text-sm text-ink2">
              {steps.length} steps · total estimated loss {formatPct2dp(totalLossPct)}% of{" "}
              {formatPct2dp(thresholdPct)}% threshold
              {plan.confidence != null &&
                ` · ${MSG_PLAN_CONFIDENCE(fractionToPct(plan.confidence))}`}
            </p>
          ) : (
            <Skeleton className="mt-1.5 h-4 w-48" />
          )}
        </div>

        <div className="flex items-center gap-2.5">
          <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-warning">
            {allDecided ? "Plan approved" : "Plan ready"}
          </span>

          <Can perm="plan.generate">
            <Button
              variant="secondary"
              onClick={() => setIsRegenerateOpen(true)}
              disabled={isLoading}
              leftIcon={<IconRefresh className="h-4 w-4" aria-hidden="true" />}
            >
              {MESSAGES.REGENERATE_PLAN}
            </Button>
          </Can>

          <Can perm="plan.approve">
            <Button
              onClick={() => setIsApproveOpen(true)}
              disabled={!allDecided || isLoading}
              leftIcon={<IconCircleCheck className="h-4 w-4" aria-hidden="true" />}
            >
              {approvePlanLabel(decidedCount, steps.length)}
            </Button>
          </Can>
        </div>
      </div>

      <AiStatusBanner status={plan?.aiStatus} message={plan?.aiMessage} />

      {/* Threshold Banner Card */}
      {plan && (
        <motion.div
          whileHover={shouldReduceMotion ? undefined : { y: -1 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="card rounded-[10px] border border-line bg-surface p-5 shadow-sm"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <strong className="text-sm font-semibold text-ink">
              Estimated total loss {formatPct2dp(totalLossPct)}% —{" "}
              {isTotalOverThreshold ? "exceeds" : "under"} the {formatPct2dp(thresholdPct)}% approval threshold.
            </strong>
            <span
              className={cx(
                "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
                isTotalOverThreshold
                  ? "bg-red-100 text-danger"
                  : "bg-emerald-100 text-success"
              )}
            >
              {formatPct2dp(totalLossPct)}% / {formatPct2dp(thresholdPct)}% threshold
            </span>
          </div>
          <div
            className="mt-3 h-2 w-full rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden"
            role="progressbar"
            aria-valuenow={totalBarWidth}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Total estimated loss against approval threshold"
          >
            <div
              className={cx(
                "h-full rounded-full transition-all duration-500",
                isTotalOverThreshold ? "bg-danger" : "bg-primary"
              )}
              style={{ width: `${Math.max(totalBarWidth > 0 ? 3 : 1, totalBarWidth)}%` }}
            />
          </div>
        </motion.div>
      )}

      {/* Action buttons (Approve all / Reject plan) */}
      <Can perm="plan.decide">
        <div className="flex items-center gap-2.5">
          <Button
            variant="primary"
            onClick={() => void handleApproveAll()}
            disabled={allDecided || isLoading}
          >
            Approve all
          </Button>
          <Button
            variant="ghost"
            onClick={handleRejectPlan}
            disabled={isLoading}
            className="text-ink2 hover:text-ink"
          >
            Reject plan
          </Button>
        </div>
      </Can>

      {overThresholdStep && (
        <div
          role="status"
          className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200"
        >
          <IconAlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
          <span>{stepExceedsThreshold(overThresholdStep.stepNo)}</span>
        </div>
      )}

      {isError ? (
        <Card>
          <EmptyState
            title="Plan unavailable"
            message={error?.detail || error?.title || "The plan could not be loaded."}
          />
        </Card>
      ) : (
        <StepTable
          steps={steps}
          lossThreshold={lossThreshold}
          canDecide={canDecide}
          loading={isLoading}
          selectedStepId={selectedStepId}
          pendingStepIds={pendingStepIds}
          onSelectStep={(step) => setSelectedStepId(step.id)}
          onDecisionChoice={handleDecisionChoice}
        />
      )}

      <AnimatePresence>
        {selectedStep && (
          <StepDiffDrawer
            step={selectedStep}
            lossThreshold={lossThreshold}
            onClose={() => setSelectedStepId(null)}
          />
        )}
      </AnimatePresence>

      <Can perm="plan.decide">
        <AnimatePresence>
          {editStep && (
            <EditStepModal
              isOpen={Boolean(editStep)}
              step={editStep}
              submitting={decideStep.isPending}
              onClose={() => setEditStep(null)}
              onConfirm={(params) => {
                const step = editStep;
                if (!step) return;
                setEditStep(null);
                void runDecision(step, "edit", { params });
              }}
            />
          )}
        </AnimatePresence>

        <AnimatePresence>
          {rejectStep && (
            <RejectReasonModal
              isOpen={Boolean(rejectStep)}
              step={rejectStep}
              submitting={decideStep.isPending}
              onClose={() => setRejectStep(null)}
              onConfirm={(reason) => {
                const step = rejectStep;
                if (!step) return;
                setRejectStep(null);
                void runDecision(step, "reject", { reason });
              }}
            />
          )}
        </AnimatePresence>
      </Can>

      <Can perm="plan.approve">
        <AnimatePresence>
          {isApproveOpen && (
            <ApproveConfirmModal
              isOpen={isApproveOpen}
              stepCount={steps.length}
              submitting={approvePlan.isPending}
              onClose={() => setIsApproveOpen(false)}
              onConfirm={() => void handleApprove()}
            />
          )}
        </AnimatePresence>
      </Can>

      <Can perm="plan.generate">
        <AnimatePresence>
          {isRegenerateOpen && (
            <Modal
              isOpen={isRegenerateOpen}
              onClose={() => setIsRegenerateOpen(false)}
              title={MESSAGES.REGENERATE_PLAN}
              maxWidth="sm"
              footer={
                <>
                  <Button
                    variant="secondary"
                    onClick={() => setIsRegenerateOpen(false)}
                    disabled={regeneratePlan.isPending}
                  >
                    {MESSAGES.CANCEL}
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() => void handleRegenerate()}
                    loading={regeneratePlan.isPending}
                  >
                    {MESSAGES.CONFIRM}
                  </Button>
                </>
              }
            >
              <p className="text-sm text-ink">{MSG_PLAN_REPLACE_CONFIRM}</p>
            </Modal>
          )}
        </AnimatePresence>
      </Can>
    </div>
  );
}

export default PlanReviewPage;
