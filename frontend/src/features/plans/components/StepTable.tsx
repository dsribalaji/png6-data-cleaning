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
import type { PlanStep } from "../../../api/schema";
import { cx, formatInt } from "../../../shared/lib/format";
import { MESSAGES } from "../../../shared/constants/messages";
import { Badge } from "../../../shared/ui/Badge";
import { RadioGroup } from "../../../shared/ui/RadioGroup";
import { Skeleton } from "../../../shared/ui/Skeleton";
import { EmptyState } from "../../../shared/ui/EmptyState";
import {
  describeStep,
  formatPct2dp,
  fractionToPct,
  getStepChoice,
  getStepLossEstimate,
  getStepLossPct,
  isStepOverThreshold,
} from "../api";
import { decisionChoiceSchema, type DecisionChoice } from "../schemas";

const DECISION_OPTIONS = [
  { value: "accept", label: MESSAGES.ACCEPT },
  { value: "edit", label: MESSAGES.EDIT },
  { value: "reject", label: MESSAGES.REJECT },
];

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
  const [draftChoice, setDraftChoice] = useState<Record<string, DecisionChoice>>({});

  const columns = useMemo<ColumnDef<PlanStep, any>[]>(() => {
    const numeric = { isNumeric: true } as const;
    const textLeft = { align: "left" } as const;

    return [
      {
        id: "stepNo",
        header: "#",
        accessorFn: (row) => row.stepNo,
        meta: numeric,
        cell: ({ getValue }) => (
          <span className="text-[#6c757d] dark:text-[#a0aec0] font-medium">
            {getValue<number>()}
          </span>
        ),
      },
      {
        id: "operation",
        header: "Operation",
        accessorFn: (row) => describeStep(row),
        meta: textLeft,
        cell: ({ row }) => (
          <div className="flex flex-col items-start gap-0.5">
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onSelectStep(row.original);
              }}
              className="rounded text-left font-medium text-[#1f2937] dark:text-[#f3f4f6] hover:text-[#fd6321] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#fd6321] px-0.5 -mx-0.5"
            >
              {describeStep(row.original)}
            </button>
            {row.original.decisionReason && (
              <span className="text-xs italic text-[#6c757d] dark:text-[#a0aec0]">
                {row.original.decisionReason}
              </span>
            )}
          </div>
        ),
      },
      {
        id: "cells",
        header: "Cells",
        accessorFn: (row) => getStepLossEstimate(row)?.cellsAffected ?? 0,
        meta: numeric,
        cell: ({ getValue }) => (
          <span className="tabular-nums">{formatInt(getValue<number>())}</span>
        ),
      },
      {
        id: "loss",
        header: "Loss",
        accessorFn: (row) => getStepLossPct(row),
        meta: numeric,
        cell: ({ row }) => {
          const overThreshold = isStepOverThreshold(row.original, lossThreshold);
          return (
            <div className="flex items-center justify-end gap-2">
              <span className="tabular-nums">
                {formatPct2dp(getStepLossPct(row.original))}
              </span>
              {overThreshold && (
                <Badge variant="danger" icon={<IconAlertTriangle className="h-3 w-3" />}>
                  High
                </Badge>
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
          if (!canDecide) {
            const persisted = getStepChoice(step, lossThreshold);
            return (
              <span className="text-sm text-[#495057] dark:text-[#cbd5e1]">
                {persisted
                  ? DECISION_OPTIONS.find((option) => option.value === persisted)?.label
                  : "—"}
              </span>
            );
          }

          const shown = draftChoice[step.id] ?? getStepChoice(step, lossThreshold);
          const isPending = pendingStepIds.includes(step.id);
          const isShownDefault = step.decision === "pending" && draftChoice[step.id] === undefined;

          const dispatchDecision = (choice: DecisionChoice) => {
            if (choice === "accept") {
              setDraftChoice((prev) => {
                const next = { ...prev };
                delete next[step.id];
                return next;
              });
            } else {
              setDraftChoice((prev) => ({ ...prev, [step.id]: choice }));
            }
            onDecisionChoice(step, choice);
          };

          return (
            <div
              className="flex items-center"
              onClick={(event) => {
                event.stopPropagation();
                if (!isShownDefault) return;
                const target = event.target as HTMLElement;
                const input =
                  target instanceof HTMLInputElement
                    ? target
                    : target.closest("label")?.querySelector("input");
                if (input?.value === "accept") {
                  dispatchDecision("accept");
                }
              }}
              role="group"
              aria-label={`Decision for step ${step.stepNo}`}
            >
              <RadioGroup
                name={`step-decision-${step.id}`}
                value={shown}
                onChange={(value) => dispatchDecision(decisionChoiceSchema.parse(value))}
                options={DECISION_OPTIONS.map((option) => ({
                  ...option,
                  disabled: isPending,
                }))}
                orientation="horizontal"
                className="gap-4"
              />
            </div>
          );
        },
      },
    ];
  }, [canDecide, draftChoice, lossThreshold, onDecisionChoice, onSelectStep, pendingStepIds]);

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
    <div className="w-full overflow-hidden rounded-lg border border-[#e9ecef] dark:border-[#343a40] bg-white dark:bg-[#24282e] shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm border-collapse">
          <caption className="sr-only">
            Cleaning plan steps with the estimated data loss for each and the decision made
          </caption>
          <thead className="bg-[#f8f9fa] dark:bg-[#1f2327] text-xs font-semibold uppercase tracking-wider text-[#6c757d] dark:text-[#a0aec0] border-b border-[#e9ecef] dark:border-[#343a40]">
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
                      className={cx("px-4 py-3.5 select-none", isNumeric && "text-right")}
                    >
                      {header.isPlaceholder ? null : canSort ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          aria-sort={
                            sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none"
                          }
                          className={cx(
                            "inline-flex items-center gap-1.5 rounded hover:text-[#1f2937] dark:hover:text-[#f3f4f6] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#fd6321]",
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

          <tbody className="divide-y divide-[#e9ecef] dark:divide-[#343a40] text-[#1f2937] dark:text-[#f3f4f6]">
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
              rows.map((row) => {
                const step = row.original;
                const isSelected = selectedStepId === step.id;
                return (
                  <tr
                    key={row.id}
                    onClick={() => onSelectStep(step)}
                    className={cx(
                      "cursor-pointer transition-colors",
                      isSelected
                        ? "bg-[#fde8e4]/60 dark:bg-[#3d2420]/60"
                        : "hover:bg-[#f8f9fa] dark:hover:bg-[#2d3239]"
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
                          className={cx("px-4 py-3", isNumeric && "text-right")}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      );
                    })}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {thresholdPct > 0 && (
        <p className="px-4 py-2.5 border-t border-[#e9ecef] dark:border-[#343a40] bg-[#f8f9fa]/50 dark:bg-[#1f2327]/30 text-xs text-[#6c757d] dark:text-[#a0aec0]">
          Loss threshold: {formatPct2dp(thresholdPct)} of cells. A step above the threshold
          is flagged <span className="font-semibold">High</span> and needs a decision before the
          plan can be approved.
        </p>
      )}
    </div>
  );
}
