import { useEffect, useMemo, useState } from "react";
import { Button } from "../../../shared/ui/Button";
import { Drawer } from "../../../shared/ui/Drawer";
import { Skeleton } from "../../../shared/ui/Skeleton";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { formatInt } from "../../../shared/lib/format";
import { MSG_CLOSE } from "../../../shared/constants/messages";
import { useQuarantine } from "../api";

const QUARANTINE_PAGE_SIZE = 20;
const ROW_REF_LABEL = "Row ref";
const REASON_LABEL = "Reason";
const NO_QUARANTINE_ROWS = "No quarantined rows were recorded for this dataset.";

export interface QuarantineDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  datasetId: string | undefined;
  quarantinedRows: number;
}

/**
 * Quarantine rows drawer (PRD Section 7, S4): row reference and reason, with
 * server-side paging because a bad ingest can quarantine thousands of rows.
 */
export function QuarantineDrawer({
  isOpen,
  onClose,
  datasetId,
  quarantinedRows,
}: QuarantineDrawerProps) {
  const [page, setPage] = useState(1);

  const { data, isPending, isFetching, isError } = useQuarantine(datasetId, {
    page,
    pageSize: QUARANTINE_PAGE_SIZE,
  });

  const total = data?.total ?? quarantinedRows;
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / QUARANTINE_PAGE_SIZE)),
    [total]
  );
  const items = data?.items ?? [];

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      title="Quarantined rows"
      subtitle={`${formatInt(total)} rows were held back during ingest because they could not be read cleanly.`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {MSG_CLOSE}
          </Button>
        </>
      }
    >
      {isPending ? (
        <div className="space-y-2" role="status" aria-label="Loading quarantined rows…">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={`quarantine-skeleton-${index}`} className="h-10 w-full" />
          ))}
        </div>
      ) : isError ? (
        <p role="alert" className="text-sm text-danger dark:text-rose-400">
          The quarantined rows could not be loaded.
        </p>
      ) : items.length === 0 ? (
        <EmptyState message={NO_QUARANTINE_ROWS} />
      ) : (
        <>
          <table className="w-full border-collapse text-left text-sm">
            <thead className="text-xs uppercase tracking-wider text-ink2 dark:text-[#a0aec0]">
              <tr className="border-b border-line dark:border-[#343a40]">
                <th scope="col" className="py-2 pr-3 font-semibold">
                  {ROW_REF_LABEL}
                </th>
                <th scope="col" className="py-2 font-semibold">
                  {REASON_LABEL}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line dark:divide-[#343a40]">
              {items.map((row) => (
                <tr key={row.id}>
                  <td className="py-2.5 pr-3 align-top tabular-nums text-ink dark:text-[#f3f4f6]">
                    {row.rowRef}
                  </td>
                  <td className="py-2.5 align-top text-ink dark:text-[#f3f4f6]">
                    {row.reason}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <nav
              aria-label="Quarantined rows pagination"
              className="mt-4 flex items-center justify-between gap-2 text-xs text-ink2 dark:text-[#a0aec0]"
            >
              <Button
                variant="secondary"
                size="sm"
                disabled={page <= 1 || isFetching}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                Previous
              </Button>
              <span className="tabular-nums">
                Page {page} of {totalPages} · {formatInt(total)} rows
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={page >= totalPages || isFetching}
                onClick={() => setPage((current) => current + 1)}
              >
                Next
              </Button>
            </nav>
          )}
        </>
      )}
    </Drawer>
  );
}

export default QuarantineDrawer;
