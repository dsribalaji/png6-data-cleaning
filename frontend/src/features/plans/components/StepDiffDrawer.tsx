import { useMemo } from "react";
import type { PlanStep } from "../../../api/schema";
import { cx, formatInt } from "../../../shared/lib/format";
import { Drawer } from "../../../shared/ui/Drawer";
import { EmptyState } from "../../../shared/ui/EmptyState";
import {
  describeStep,
  formatPct2dp,
  fractionToPct,
  getStepLossEstimate,
  isStepOverThreshold,
} from "../api";

const MAX_SAMPLE_ROWS = 5;

type SampleRow = Record<string, unknown>;

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function isSameValue(before: unknown, after: unknown): boolean {
  if (before === after) return true;
  if (before === null || before === undefined || before === "") {
    return after === null || after === undefined || after === "";
  }
  return false;
}

function collectColumns(before: SampleRow[], after: SampleRow[]): string[] {
  const columns: string[] = [];
  for (const row of [...before, ...after]) {
    for (const key of Object.keys(row)) {
      if (!columns.includes(key)) columns.push(key);
    }
  }
  return columns;
}

export interface StepDiffDrawerProps {
  step: PlanStep | null;
  lossThreshold: number;
  onClose: () => void;
}

/**
 * Right-hand drawer for a single step (wireframe 1g): why the model proposed it,
 * how confident it was, what the data looks like before and after, and how much
 * of the dataset the step is estimated to destroy.
 */
export function StepDiffDrawer({ step, lossThreshold, onClose }: StepDiffDrawerProps) {
  const isOpen = Boolean(step);

  const diff = useMemo(() => {
    if (!step) {
      return { before: [] as SampleRow[], after: [] as SampleRow[], columns: [] as string[] };
    }
    const before = (step.sampleBefore ?? []).slice(0, MAX_SAMPLE_ROWS);
    const after = (step.sampleAfter ?? []).slice(0, MAX_SAMPLE_ROWS);
    return { before, after, columns: collectColumns(before, after) };
  }, [step]);

  if (!step) {
    return null;
  }

  const loss = getStepLossEstimate(step);
  const lossPct = fractionToPct(loss?.estimatedLoss);
  const thresholdPct = fractionToPct(lossThreshold);
  const overThreshold = isStepOverThreshold(step, lossThreshold);
  const barScale = Math.max(lossPct, thresholdPct * 2, 0.01);
  const changedColumns = step.changedColumns ?? [];
  const hasSamples = diff.columns.length > 0;

  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      width="xl"
      title={describeStep(step)}
      subtitle={`Step ${step.stepNo} · ${step.operation.replace(/_/g, " ")}`}
    >
      <div className="space-y-6">
        <section aria-labelledby="drawer-rationale">
          <h4
            id="drawer-rationale"
            className="text-xs font-semibold uppercase tracking-wider text-[#6c757d] dark:text-[#a0aec0]"
          >
            Rationale
          </h4>
          <p className="mt-1.5 text-sm text-[#1f2937] dark:text-[#f3f4f6] leading-relaxed">
            {step.rationale}
          </p>
        </section>

        <section aria-labelledby="drawer-confidence">
          <h4
            id="drawer-confidence"
            className="text-xs font-semibold uppercase tracking-wider text-[#6c757d] dark:text-[#a0aec0]"
          >
            Confidence
          </h4>
          <p className="mt-1.5 text-sm font-semibold text-[#1f2937] dark:text-[#f3f4f6] tabular-nums">
            {formatPct2dp(fractionToPct(step.confidence))}
          </p>
        </section>

        <section aria-labelledby="drawer-loss">
          <h4
            id="drawer-loss"
            className="text-xs font-semibold uppercase tracking-wider text-[#6c757d] dark:text-[#a0aec0]"
          >
            Estimated loss
          </h4>
          <p className="mt-1.5 text-sm text-[#1f2937] dark:text-[#f3f4f6] tabular-nums">
            {formatPct2dp(lossPct)} of cells
          </p>

          <div className="mt-3">
            <div
              className="relative h-2.5 w-full overflow-hidden rounded-full bg-[#e9ecef] dark:bg-[#343a40]"
              role="img"
              aria-label={`Estimated loss ${formatPct2dp(lossPct)} of cells against a threshold of ${formatPct2dp(thresholdPct)}`}
            >
              <div
                className={cx(
                  "absolute inset-y-0 left-0 rounded-full",
                  overThreshold
                    ? "bg-rose-500 dark:bg-rose-400"
                    : "bg-[#fd6321]"
                )}
                style={{ width: `${Math.min(100, (lossPct / barScale) * 100)}%` }}
              />
              {thresholdPct > 0 && (
                <div
                  className="absolute inset-y-0 w-0.5 bg-[#1f2937] dark:bg-white"
                  style={{ left: `${Math.min(100, (thresholdPct / barScale) * 100)}%` }}
                  aria-hidden="true"
                />
              )}
            </div>
            <p className="mt-1.5 text-xs text-[#6c757d] dark:text-[#a0aec0]">
              Loss threshold: {formatPct2dp(thresholdPct)} of cells
            </p>
          </div>

          <dl className="mt-4 grid grid-cols-3 gap-3">
            {[
              { label: "Rows", value: loss?.rowsAffected },
              { label: "Columns", value: loss?.columnsAffected },
              { label: "Cells", value: loss?.cellsAffected },
            ].map((item) => (
              <div
                key={item.label}
                className="rounded-md border border-[#e9ecef] dark:border-[#343a40] bg-[#f8f9fa] dark:bg-[#1f2327] px-3 py-2"
              >
                <dt className="text-[11px] font-semibold uppercase tracking-wider text-[#6c757d] dark:text-[#a0aec0]">
                  {item.label}
                </dt>
                <dd className="mt-0.5 text-sm font-semibold tabular-nums text-[#1f2937] dark:text-[#f3f4f6]">
                  {formatInt(item.value)}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        <section aria-labelledby="drawer-sample">
          <h4
            id="drawer-sample"
            className="text-xs font-semibold uppercase tracking-wider text-[#6c757d] dark:text-[#a0aec0]"
          >
            Sample before and after
          </h4>

          {!hasSamples ? (
            <EmptyState
              className="mt-2"
              message="No sample rows are available for this step."
            />
          ) : (
            <>
              <p className="mt-1.5 text-xs text-[#6c757d] dark:text-[#a0aec0]">
                Up to {MAX_SAMPLE_ROWS} rows. Changed cells are highlighted.
              </p>
              <div className="mt-2 overflow-x-auto rounded-lg border border-[#e9ecef] dark:border-[#343a40]">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-[#f8f9fa] dark:bg-[#1f2327] text-[#6c757d] dark:text-[#a0aec0] border-b border-[#e9ecef] dark:border-[#343a40]">
                    <tr>
                      <th scope="col" className="px-3 py-2.5 font-semibold uppercase tracking-wider">
                        Version
                      </th>
                      {diff.columns.map((column) => (
                        <th
                          key={column}
                          scope="col"
                          className="px-3 py-2.5 font-semibold uppercase tracking-wider whitespace-nowrap"
                        >
                          {column}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#e9ecef] dark:divide-[#343a40] text-[#1f2937] dark:text-[#f3f4f6]">
                    {diff.before.map((row, index) => (
                      <tr key={`before-${index}`}>
                        <th
                          scope="row"
                          className="px-3 py-2 font-semibold text-[#6c757d] dark:text-[#a0aec0] whitespace-nowrap"
                        >
                          Before
                        </th>
                        {diff.columns.map((column) => (
                          <td key={column} className="px-3 py-2 whitespace-nowrap">
                            {formatCellValue(row[column])}
                          </td>
                        ))}
                      </tr>
                    ))}
                    {diff.after.map((row, index) => (
                      <tr key={`after-${index}`}>
                        <th
                          scope="row"
                          className="px-3 py-2 font-semibold text-[#6c757d] dark:text-[#a0aec0] whitespace-nowrap"
                        >
                          After
                        </th>
                        {diff.columns.map((column) => {
                          const beforeValue = diff.before[index]?.[column];
                          const afterValue = row[column];
                          const changed =
                            changedColumns.includes(column) ||
                            !isSameValue(beforeValue, afterValue);

                          return (
                            <td
                              key={column}
                              className={cx(
                                "px-3 py-2 whitespace-nowrap",
                                changed &&
                                  "bg-amber-100 dark:bg-amber-950/60 font-medium text-amber-900 dark:text-amber-200"
                              )}
                            >
                              {formatCellValue(afterValue)}
                              {changed && <span className="sr-only"> (changed)</span>}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      </div>
    </Drawer>
  );
}
