import { useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { IconChevronDown, IconChevronRight, IconFlask2 } from "@tabler/icons-react";
import { Badge, type BadgeVariant } from "../../../shared/ui/Badge";
import { DataTable } from "../../../shared/ui/DataTable";
import { Skeleton } from "../../../shared/ui/Skeleton";
import { cx, formatInt } from "../../../shared/lib/format";
import type {
  TestOutcome,
  TestRunRow,
  TestSuite,
  TestSuiteSummary,
  Validation,
} from "../api";

// PRD S6 copy. Only the strings the PRD fixes word-for-word live in
// messages.ts; these column headers and labels are declared next to their use.
const UNIT_LABEL = "Unit";
const INTEGRATION_LABEL = "Integration";
const NAME_LABEL = "Name";
const TARGET_STEP_LABEL = "Target step";
const RESULT_LABEL = "Result";
const RUN_TIME_LABEL = "Run time (ms)";
const NO_VALUE = "—";
const NO_TESTS = "No tests were generated for this suite.";
const CLICK_HINT = "Click a tile to see the list of tests.";

/** Result badge copy. Colour is never the only signal (WCAG 2.1 AA). */
export const TEST_OUTCOME_LABEL: Record<TestOutcome, string> = {
  passed: "Passed",
  failed: "Failed",
  error: "Error",
  not_run: "Not run",
};

export const TEST_OUTCOME_VARIANT: Record<TestOutcome, BadgeVariant> = {
  passed: "success",
  failed: "danger",
  error: "danger",
  not_run: "secondary",
};

const SUITE_LABEL: Record<TestSuite, string> = {
  unit: UNIT_LABEL,
  integration: INTEGRATION_LABEL,
};

const TEST_PAGE_SIZE = 20;

interface SuiteEntry {
  suite: TestSuite;
  summary: TestSuiteSummary;
}

export interface TestSummaryProps {
  validation: Validation | undefined;
  loading?: boolean;
}

/** `12/13` — the PRD tile figures, right-aligned by convention elsewhere. */
function tileValue(summary: TestSuiteSummary): string {
  return `${formatInt(summary.passed)}/${formatInt(summary.total)}`;
}

/**
 * KPI-tile shaped button (spec card, interactive):
 * clicking expands the test list underneath the tiles.
 */
function TestTile({
  suite,
  summary,
  expanded,
  onToggle,
}: {
  suite: TestSuite;
  summary: TestSuiteSummary;
  expanded: boolean;
  onToggle: () => void;
}) {
  const noTests = summary.total === 0;
  const isGreen = !noTests && summary.passed >= summary.total;
  const stateVariant: BadgeVariant = noTests ? "secondary" : isGreen ? "success" : "danger";
  const stateLabel = noTests ? "No tests" : isGreen ? "All passed" : "Not all passed";

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={expanded}
      className={cx(
        "flex items-center justify-between gap-4 rounded-[10px] border bg-surface p-5 shadow-sm text-left transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
        expanded
          ? "border-primary ring-1 ring-primary"
          : "border-line hover:border-primary hover:-translate-y-px"
      )}
    >
      <span className="min-w-0 flex-1">
        <span className="block text-xs font-semibold uppercase tracking-wider text-ink2 truncate">
          {SUITE_LABEL[suite]}
        </span>
        <span className="mt-1.5 block text-2xl font-bold tracking-tight tabular-nums text-ink">
          {tileValue(summary)}
        </span>
      </span>

      <span className="flex flex-shrink-0 items-center gap-2">
        <Badge variant={stateVariant}>{stateLabel}</Badge>
        <span
          className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-primary"
          aria-hidden="true"
        >
          {expanded ? (
            <IconChevronDown className="h-5 w-5" />
          ) : (
            <IconChevronRight className="h-5 w-5" />
          )}
        </span>
      </span>
    </button>
  );
}

const testColumns: ColumnDef<TestRunRow, any>[] = [
  {
    id: "name",
    header: NAME_LABEL,
    cell: ({ row }) => (
      <span className="font-medium text-ink">
        {row.original.name}
      </span>
    ),
  },
  {
    id: "targetStepNo",
    header: TARGET_STEP_LABEL,
    meta: { align: "right" },
    cell: ({ row }) =>
      row.original.targetStepNo === null ? NO_VALUE : formatInt(row.original.targetStepNo),
  },
  {
    id: "outcome",
    header: RESULT_LABEL,
    cell: ({ row }) => (
      <Badge variant={TEST_OUTCOME_VARIANT[row.original.outcome]}>
        {TEST_OUTCOME_LABEL[row.original.outcome]}
      </Badge>
    ),
  },
  {
    id: "durationMs",
    header: RUN_TIME_LABEL,
    meta: { align: "right" },
    cell: ({ row }) =>
      row.original.durationMs === null ? NO_VALUE : formatInt(row.original.durationMs),
  },
];

/**
 * S6 test tiles (PRD Section 7, wireframe 1i, preview.html spec): Unit passed/total and
 * Integration passed/total. Clicking a tile expands its test list — name,
 * target step, result badge, run time in milliseconds.
 */
export function TestSummary({ validation, loading = false }: TestSummaryProps) {
  const [openSuite, setOpenSuite] = useState<TestSuite | null>(null);

  const suites: SuiteEntry[] = validation
    ? [
        { suite: "unit", summary: validation.unit },
        { suite: "integration", summary: validation.integration },
      ]
    : [];

  const open = suites.find((entry) => entry.suite === openSuite) ?? null;

  if (loading || !validation) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Skeleton className="h-24 rounded-[10px]" />
          <Skeleton className="h-24 rounded-[10px]" />
        </div>
        <p className="text-xs text-ink2">{CLICK_HINT}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {suites.map((entry) => (
          <TestTile
            key={entry.suite}
            suite={entry.suite}
            summary={entry.summary}
            expanded={openSuite === entry.suite}
            onToggle={() =>
              setOpenSuite((current) => (current === entry.suite ? null : entry.suite))
            }
          />
        ))}
      </div>

      {open && (
        <section aria-label={`${SUITE_LABEL[open.suite]} tests`}>
          <div className="mb-2.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink2">
            <IconFlask2 className="h-4 w-4 text-primary" aria-hidden="true" />
            <span>{SUITE_LABEL[open.suite]}</span>
            <span className="font-normal normal-case tracking-normal text-muted">
              ({tileValue(open.summary)})
            </span>
          </div>
          <DataTable
            // Keyed by suite so switching tiles starts back on page one.
            key={open.suite}
            columns={testColumns}
            data={open.summary.tests}
            pageSize={TEST_PAGE_SIZE}
            emptyMessage={NO_TESTS}
          />
        </section>
      )}
    </div>
  );
}

export default TestSummary;