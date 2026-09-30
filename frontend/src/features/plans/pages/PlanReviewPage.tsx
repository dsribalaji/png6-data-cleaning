import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { IconAlertTriangle, IconRefresh, IconCircleCheck } from "@tabler/icons-react";
import type { PlanStep } from "../../../api/schema";
import { Can } from "../../../auth/Can";
import { usePermission } from "../../../auth/permissions";
import {
  MESSAGES,
  MSG_PLAN_REPLACE_CONFIRM,
  approvePlanLabel,
  stepExceedsThreshold,
  totalEstLoss,
} from "../../../shared/constants/messages";
import { Button } from "../../../shared/ui/Button";
import { Card } from "../../../shared/ui/Card";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { Modal } from "../../../shared/ui/Modal";
import { Skeleton } from "../../../shared/ui/Skeleton";
import { useToast } from "../../../shared/ui/Toast";
import {
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
import { StepTable } from "../components/StepTable";

export function PlanReviewPage() {
  const { id = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();

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

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[#1f2937] dark:text-[#f3f4f6]">
            Plan review
          </h1>
          {plan ? (
            <p className="mt-1 text-sm text-[#6c757d] dark:text-[#a0aec0]">
              {totalEstLoss(fractionToPct(plan.totalEstimatedLoss))}
            </p>
          ) : (
            <Skeleton className="mt-1.5 h-4 w-48" />
          )}
        </div>

        <div className="flex items-center gap-3">
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

      <StepDiffDrawer
        step={selectedStep}
        lossThreshold={lossThreshold}
        onClose={() => setSelectedStepId(null)}
      />

      <Can perm="plan.decide">
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
      </Can>

      <Can perm="plan.approve">
        <ApproveConfirmModal
          isOpen={isApproveOpen}
          stepCount={steps.length}
          submitting={approvePlan.isPending}
          onClose={() => setIsApproveOpen(false)}
          onConfirm={() => void handleApprove()}
        />
      </Can>

      <Can perm="plan.generate">
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
          <p className="text-sm text-[#1f2937] dark:text-[#f3f4f6]">
            {MSG_PLAN_REPLACE_CONFIRM}
          </p>
        </Modal>
      </Can>
    </div>
  );
}

export default PlanReviewPage;
