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
import { isNeverAutoStep } from "./StepTable";

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
 * Right-hand drawer for a single step (wireframe 1g, preview.html spec):
 * rationale, confidence, estimated loss, before/after diff samples, and
 * human approval tags.
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
  const isNeverAuto = isNeverAutoStep(step);

  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      width="xl"
      title={describeStep(step)}
      subtitle={`Step ${step.stepNo} · ${step.operation.replace(/_/g, " ")}`}
    >
      <div className="space-y-6 text-ink">
        <section aria-labelledby="drawer-rationale">
          <h4
            id="drawer-rationale"
            className="text-xs font-semibold uppercase tracking-wider text-ink2"
          >
            Rationale
          </h4>
          <p className="mt-1.5 text-sm text-ink leading-relaxed">
            {step.rationale}
          </p>
          {isNeverAuto && (
            <div className="mt-2.5">
              <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-warning">
                NEVER auto-approved — human decision required
              </span>
            </div>
          )}
        </section>

        <section aria-labelledby="drawer-confidence">
          <h4
            id="drawer-confidence"
            className="text-xs font-semibold uppercase tracking-wider text-ink2"
          >
            Confidence
          </h4>
          <p className="mt-1.5 text-sm font-semibold tabular-nums text-ink">
            {formatPct2dp(fractionToPct(step.confidence))}
          </p>
        </section>

        <section aria-labelledby="drawer-loss">
          <h4
            id="drawer-loss"
            className="text-xs font-semibold uppercase tracking-wider text-ink2"
          >
            Estimated loss
          </h4>
          <p className="mt-1.5 text-sm tabular-nums text-ink">
            {formatPct2dp(lossPct)} of cells
          </p>

          <div className="mt-3">
            <div
              className="relative h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
              role="img"
              aria-label={`Estimated loss ${formatPct2dp(lossPct)} of cells against a threshold of ${formatPct2dp(thresholdPct)}`}
            >
              <div
                className={cx(
                  "absolute inset-y-0 left-0 rounded-full transition-all duration-300",
                  overThreshold ? "bg-danger" : "bg-primary"
                )}
                style={{ width: `${Math.min(100, (lossPct / barScale) * 100)}%` }}
              />
              {thresholdPct > 0 && (
                <div
                  className="absolute inset-y-0 w-0.5 bg-ink"
                  style={{ left: `${Math.min(100, (thresholdPct / barScale) * 100)}%` }}
                  aria-hidden="true"
                />
              )}
            </div>
            <p className="mt-1.5 text-xs text-ink2">
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
                className="rounded-lg border border-line bg-canvas px-3 py-2"
              >
                <dt className="text-[11px] font-semibold uppercase tracking-wider text-ink2">
                  {item.label}
                </dt>
                <dd className="mt-0.5 text-sm font-semibold tabular-nums text-ink">
                  {formatInt(item.value)}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        <section aria-labelledby="drawer-sample">
          <h4
            id="drawer-sample"
            className="text-xs font-semibold uppercase tracking-wider text-ink2"
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
              <p className="mt-1.5 text-xs text-ink2">
                Up to {MAX_SAMPLE_ROWS} rows. Changed cells are highlighted.
              </p>
              <div className="mt-2 overflow-x-auto rounded-lg border border-line bg-surface">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="border-b border-line bg-canvas text-ink2">
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
                  <tbody className="divide-y divide-line text-ink">
                    {diff.before.map((row, index) => (
                      <tr key={`before-${index}`}>
                        <th
                          scope="row"
                          className="px-3 py-2 font-semibold text-ink2 whitespace-nowrap"
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
                          className="px-3 py-2 font-semibold text-ink2 whitespace-nowrap"
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

export default StepDiffDrawer;
