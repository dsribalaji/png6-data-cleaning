import { useMemo, useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { IconAlertTriangle } from "@tabler/icons-react";
import { motion, useReducedMotion } from "motion/react";
import type { PlanStep } from "../../../api/schema";
import { cx } from "../../../shared/lib/format";
import { MSG_AI_TAG, MSG_AI_TAG_TITLE } from "../../../shared/constants/messages";
import { Badge } from "../../../shared/ui/Badge";
import { Button } from "../../../shared/ui/Button";
import { Skeleton } from "../../../shared/ui/Skeleton";
import { EmptyState } from "../../../shared/ui/EmptyState";
import {
  describeStep,
  formatPct2dp,
  fractionToPct,
  getStepChoice,
  getStepLossPct,
  isStepOverThreshold,
} from "../api";
import type { DecisionChoice } from "../schemas";

export interface StepTableProps {
  steps: PlanStep[];
  lossThreshold: number;
  canDecide: boolean;
  loading?: boolean;
  selectedStepId?: string | null;
  pendingStepIds?: readonly string[];
  onSelectStep: (step: PlanStep) => void;
  onDecisionChoice: (step: PlanStep, choice: DecisionChoice) => void;
}

/** Operations that must be human-decided and never automatically accepted. */
export function isNeverAutoStep(step: PlanStep): boolean {
  const op = step.operation?.toLowerCase();
  return (
    op === "fill_missing" ||
    op === "derive_column" ||
    op === "cross_field_fill" ||
    Boolean(step.parameters && (step.parameters as Record<string, unknown>).neverAuto)
  );
}

export function StepTable({
  steps,
  lossThreshold,
  canDecide,
  loading = false,
  selectedStepId = null,
  pendingStepIds = [],
  onSelectStep,
  onDecisionChoice,
}: StepTableProps) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "stepNo", desc: false }]);
  const shouldReduceMotion = useReducedMotion();

  const columns = useMemo<ColumnDef<PlanStep, any>[]>(() => {
    const numeric = { isNumeric: true } as const;
    const textLeft = { align: "left" } as const;

    return [
      {
        id: "stepNo",
        header: "Step",
        accessorFn: (row) => row.stepNo,
        meta: numeric,
        cell: ({ getValue }) => (
          <span className="font-bold text-ink">
            {getValue<number>()}
          </span>
        ),
      },
      {
        id: "operation",
        header: "Operation",
        accessorFn: (row) => describeStep(row),
        meta: textLeft,
        cell: ({ row }) => {
          const step = row.original;
          return (
            <div className="flex flex-col items-start gap-1">
              <span className="font-medium text-ink">
                {step.operation.replace(/_/g, " ")}
              </span>
              {step.source === "llm" && (
                <Badge variant="info" title={MSG_AI_TAG_TITLE}>
                  {MSG_AI_TAG}
                </Badge>
              )}
              {step.decisionReason && (
                <span className="text-xs italic text-ink2">
                  {step.decisionReason}
                </span>
              )}
            </div>
          );
        },
      },
      {
        id: "target",
        header: "Target",
        meta: textLeft,
        cell: ({ row }) => {
          const cols = row.original.changedColumns ?? [];
          const targetText = cols.length > 0 ? cols.join(", ") : "all";
          return (
            <code className="rounded bg-canvas px-1.5 py-0.5 font-mono text-xs text-ink2 border border-line">
              {targetText}
            </code>
          );
        },
      },
      {
        id: "loss",
        header: "Est. loss",
        accessorFn: (row) => getStepLossPct(row),
        meta: textLeft,
        cell: ({ row }) => {
          const step = row.original;
          const lossPct = getStepLossPct(step);
          const thresholdPct = fractionToPct(lossThreshold);
          const overThreshold = isStepOverThreshold(step, lossThreshold);
          // Bar width = (loss / threshold) * 100
          const barWidth =
            thresholdPct > 0 ? Math.min(100, Math.round((lossPct / thresholdPct) * 100)) : 0;

          return (
            <div className="flex items-center gap-2">
              <span className="min-w-[36px] text-xs tabular-nums text-ink">
                {formatPct2dp(lossPct)}
              </span>
              <div
                className="h-2 w-24 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden flex-shrink-0"
                role="progressbar"
                aria-valuenow={barWidth}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Loss for step ${step.stepNo}`}
              >
                <div
                  className={cx(
                    "h-full rounded-full transition-all duration-300",
                    overThreshold ? "bg-danger" : "bg-primary"
                  )}
                  style={{ width: `${Math.max(barWidth > 0 ? 3 : 1, barWidth)}%` }}
                />
              </div>
              {overThreshold && (
                <span className="inline-flex items-center gap-1 rounded bg-red-100 px-1.5 py-0.5 text-[11px] font-semibold text-danger">
                  <IconAlertTriangle className="h-3 w-3" aria-hidden="true" />
                  High
                </span>
              )}
            </div>
          );
        },
      },
      {
        id: "decision",
        header: "Decision",
        enableSorting: false,
        meta: textLeft,
        cell: ({ row }) => {
          const step = row.original;
          const isPending = pendingStepIds.includes(step.id);
          const choice = getStepChoice(step, lossThreshold);
          const isNeverAuto = isNeverAutoStep(step);

          if (!canDecide) {
            if (choice === "accept") {
              return (
                <span className="inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-success">
                  Approved
                </span>
              );
            }
            if (choice === "reject") {
              return (
                <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-danger">
                  Rejected
                </span>
              );
            }
            if (choice === "edit") {
              return (
                <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-info">
                  Edited
                </span>
              );
            }
            return (
              <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-ink2">
                {isNeverAuto ? "Pending — never auto" : "Pending"}
              </span>
            );
          }

          return (
            <div
              className="inline-flex flex-wrap items-center gap-1.5"
              onClick={(e) => e.stopPropagation()}
            >
              {choice === "accept" ? (
                <>
                  <span className="inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-success">
                    Approved
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isPending}
                    onClick={() => onDecisionChoice(step, "reject")}
                    className="text-xs text-ink2 hover:text-ink"
                  >
                    Reject
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isPending}
                    onClick={() => onDecisionChoice(step, "edit")}
                    className="text-xs text-ink2 hover:text-ink"
                  >
                    Edit
                  </Button>
                </>
              ) : choice === "reject" ? (
                <>
                  <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-danger">
                    Rejected
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isPending}
                    onClick={() => onDecisionChoice(step, "accept")}
                    className="text-xs text-ink2 hover:text-ink"
                  >
                    Approve
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isPending}
                    onClick={() => onDecisionChoice(step, "edit")}
                    className="text-xs text-ink2 hover:text-ink"
                  >
                    Edit
                  </Button>
                </>
              ) : choice === "edit" ? (
                <>
                  <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-info">
                    Edited
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isPending}
                    onClick={() => onDecisionChoice(step, "accept")}
                    className="text-xs text-ink2 hover:text-ink"
                  >
                    Approve
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isPending}
                    onClick={() => onDecisionChoice(step, "reject")}
                    className="text-xs text-ink2 hover:text-ink"
                  >
                    Reject
                  </Button>
                </>
              ) : (
                <>
                  <span
                    className={cx(
                      "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
                      isNeverAuto
                        ? "bg-amber-100 text-warning"
                        : "bg-slate-100 text-ink2"
                    )}
                  >
                    {isNeverAuto ? "Pending — never auto" : "Pending"}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isPending}
                    onClick={() => onDecisionChoice(step, "accept")}
                    className="text-xs text-ink2 hover:text-ink"
                  >
                    Approve
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isPending}
                    onClick={() => onDecisionChoice(step, "reject")}
                    className="text-xs text-ink2 hover:text-ink"
                  >
                    Reject
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isPending}
                    onClick={() => onDecisionChoice(step, "edit")}
                    className="text-xs text-ink2 hover:text-ink"
                  >
                    Edit
                  </Button>
                </>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onSelectStep(step)}
                className="text-xs text-ink2 hover:text-ink"
              >
                Details
              </Button>
            </div>
          );
        },
      },
    ];
  }, [canDecide, lossThreshold, onDecisionChoice, onSelectStep, pendingStepIds]);

  const table = useReactTable({
    data: steps,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const rows = table.getRowModel().rows;
  const thresholdPct = fractionToPct(lossThreshold);

  return (
    <div className="card rounded-[10px] border border-line bg-surface p-5 shadow-sm transition-transform hover:-translate-y-px">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-semibold text-ink">Steps</h2>
        <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-ink2">
          Click row for diff details
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm border-collapse">
          <caption className="sr-only">
            Cleaning plan steps with the estimated data loss for each and the decision made
          </caption>
          <thead className="border-b border-line bg-canvas text-xs font-semibold uppercase tracking-wider text-ink2">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const meta = header.column.columnDef.meta as
                    | { isNumeric?: boolean; align?: "left" | "center" | "right" }
                    | undefined;
                  const isNumeric = meta?.isNumeric || meta?.align === "right";
                  const canSort = header.column.getCanSort();
                  const sorted = header.column.getIsSorted();

                  return (
                    <th
                      key={header.id}
                      scope="col"
                      className={cx("px-4 py-3 select-none", isNumeric && "text-right")}
                    >
                      {header.isPlaceholder ? null : canSort ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          aria-sort={
                            sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none"
                          }
                          className={cx(
                            "inline-flex items-center gap-1.5 rounded hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                            isNumeric && "flex-row-reverse"
                          )}
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          <span className="sr-only">
                            {sorted === "asc"
                              ? "sorted ascending"
                              : sorted === "desc"
                                ? "sorted descending"
                                : "not sorted"}
                          </span>
                        </button>
                      ) : (
                        flexRender(header.column.columnDef.header, header.getContext())
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>

          <tbody className="divide-y divide-line text-ink">
            {loading ? (
              Array.from({ length: 5 }).map((_, rowIndex) => (
                <tr key={`step-skeleton-${rowIndex}`} className="animate-pulse">
                  {columns.map((_, cellIndex) => (
                    <td key={`step-skeleton-${rowIndex}-${cellIndex}`} className="px-4 py-3.5">
                      <Skeleton className="h-4 w-full max-w-[140px]" />
                    </td>
                  ))}
                </tr>
              ))
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="p-8 text-center">
                  <EmptyState message="This plan has no steps to decide." />
                </td>
              </tr>
            ) : (
              rows.map((row, index) => {
                const step = row.original;
                const isSelected = selectedStepId === step.id;
                return (
                  <motion.tr
                    key={row.id}
                    initial={shouldReduceMotion ? false : { opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                      duration: 0.22,
                      ease: "easeOut",
                      delay: shouldReduceMotion ? 0 : index * 0.04,
                    }}
                    onClick={() => onSelectStep(step)}
                    className={cx(
                      "cursor-pointer transition-colors",
                      isSelected
                        ? "bg-indigo-50/70 dark:bg-indigo-950/40"
                        : "hover:bg-slate-50 dark:hover:bg-slate-800/50"
                    )}
                  >
                    {row.getVisibleCells().map((cell) => {
                      const meta = cell.column.columnDef.meta as
                        | { isNumeric?: boolean; align?: "left" | "center" | "right" }
                        | undefined;
                      const isNumeric = meta?.isNumeric || meta?.align === "right";

                      return (
                        <td
                          key={cell.id}
                          className={cx("px-4 py-3 align-middle", isNumeric && "text-right")}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      );
                    })}
                  </motion.tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {thresholdPct > 0 && (
        <p className="mt-3 border-t border-line pt-3 text-xs text-ink2">
          Loss threshold: {formatPct2dp(thresholdPct)} of cells. A step above the threshold
          is flagged <span className="font-semibold text-danger">High</span> and needs a decision before the
          plan can be approved.
        </p>
      )}
    </div>
  );
}

export default StepTable;
