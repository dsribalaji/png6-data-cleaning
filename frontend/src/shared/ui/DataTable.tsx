import { useState, useMemo } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import {
  IconChevronUp,
  IconChevronDown,
  IconSelector,
  IconChevronLeft,
  IconChevronRight,
} from "@tabler/icons-react";
import { motion, useReducedMotion } from "motion/react";
import { cx } from "../lib/format";
import { Skeleton } from "./Skeleton";
import { EmptyState } from "./EmptyState";
import { Button } from "./Button";

export interface DataTableColumnMeta {
  isNumeric?: boolean;
  align?: "left" | "center" | "right";
  className?: string;
}

export interface DataTableProps<TData> {
  columns: ColumnDef<TData, any>[];
  data: TData[];
  pageSize?: number;
  loading?: boolean;
  emptyMessage?: string;
  emptyTitle?: string;
  onRowClick?: (row: TData) => void;
  className?: string;
}

export function DataTable<TData>({
  columns,
  data,
  pageSize = 20,
  loading = false,
  emptyMessage = "No records found.",
  emptyTitle,
  onRowClick,
  className,
}: DataTableProps<TData>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [pagination, setPagination] = useState({
    pageIndex: 0,
    pageSize,
  });

  const shouldReduceMotion = useReducedMotion();
  const tableData = useMemo(() => data, [data]);

  const table = useReactTable({
    data: tableData,
    columns,
    state: {
      sorting,
      pagination,
    },
    onSortingChange: setSorting,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  const rows = table.getRowModel().rows;
  const pageCount = table.getPageCount();
  const pageIndex = table.getState().pagination.pageIndex;
  const totalRows = tableData.length;

  return (
    <div
      className={cx(
        "w-full overflow-hidden rounded-[10px] border border-line dark:border-[#343a40] bg-surface dark:bg-[#24282e] shadow-sm transition-colors",
        className
      )}
    >
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm border-collapse">
          <thead className="bg-canvas dark:bg-[#1f2327] text-xs font-semibold uppercase tracking-wider text-ink2 dark:text-[#a0aec0] border-b border-line dark:border-[#343a40]">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const meta = header.column.columnDef.meta as DataTableColumnMeta | undefined;
                  const isNumeric = meta?.isNumeric || meta?.align === "right";
                  const canSort = header.column.getCanSort();
                  const sorted = header.column.getIsSorted();

                  return (
                    <th
                      key={header.id}
                      scope="col"
                      colSpan={header.colSpan}
                      className={cx(
                        "px-4 py-3.5 select-none transition-colors",
                        isNumeric && "text-right",
                        meta?.className
                      )}
                    >
                      {header.isPlaceholder ? null : canSort ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          className={cx(
                            "inline-flex items-center gap-1.5 hover:text-ink dark:hover:text-[#f3f4f6] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary rounded",
                            isNumeric && "flex-row-reverse"
                          )}
                          title={`Sort by ${String(header.column.columnDef.header || "")}`}
                        >
                          <span>
                            {flexRender(
                              header.column.columnDef.header,
                              header.getContext()
                            )}
                          </span>
                          <span className="flex-shrink-0 text-ink2 dark:text-[#a0aec0]">
                            {sorted === "asc" ? (
                              <IconChevronUp className="h-3.5 w-3.5" aria-hidden="true" />
                            ) : sorted === "desc" ? (
                              <IconChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
                            ) : (
                              <IconSelector className="h-3.5 w-3.5 opacity-60" aria-hidden="true" />
                            )}
                          </span>
                        </button>
                      ) : (
                        <div>
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                        </div>
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>

          <tbody className="divide-y divide-line dark:divide-[#343a40] text-ink dark:text-[#f3f4f6]">
            {loading ? (
              Array.from({ length: Math.min(pageSize, 5) }).map((_, rIndex) => (
                <tr key={`loading-row-${rIndex}`} className="animate-pulse">
                  {columns.map((_, cIndex) => (
                    <td key={`loading-cell-${cIndex}`} className="px-4 py-3.5">
                      <Skeleton className="h-4 w-full max-w-[120px]" />
                    </td>
                  ))}
                </tr>
              ))
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="p-8 text-center">
                  <EmptyState title={emptyTitle} message={emptyMessage} />
                </td>
              </tr>
            ) : (
              rows.map((row, index) => (
                <motion.tr
                  key={row.id}
                  initial={shouldReduceMotion ? false : { opacity: 0, y: 4 }}
                  animate={shouldReduceMotion ? undefined : { opacity: 1, y: 0 }}
                  transition={
                    shouldReduceMotion
                      ? undefined
                      : { delay: index * 0.04, duration: 0.22, ease: "easeOut" }
                  }
                  onClick={() => onRowClick?.(row.original)}
                  className={cx(
                    "hover:bg-canvas dark:hover:bg-[#2d3239] transition-colors",
                    onRowClick && "cursor-pointer"
                  )}
                >
                  {row.getVisibleCells().map((cell) => {
                    const meta = cell.column.columnDef.meta as DataTableColumnMeta | undefined;
                    const isNumeric = meta?.isNumeric || meta?.align === "right";

                    return (
                      <td
                        key={cell.id}
                        className={cx(
                          "px-4 py-3 text-sm",
                          isNumeric && "text-right tabular-nums",
                          meta?.className
                        )}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    );
                  })}
                </motion.tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Bar */}
      {!loading && totalRows > pageSize && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-line dark:border-[#343a40] bg-canvas/50 dark:bg-[#1f2327]/30 text-xs text-ink2 dark:text-[#a0aec0]">
          <div>
            Showing{" "}
            <span className="font-semibold text-ink dark:text-[#f3f4f6]">
              {pageIndex * pageSize + 1}
            </span>{" "}
            to{" "}
            <span className="font-semibold text-ink dark:text-[#f3f4f6]">
              {Math.min((pageIndex + 1) * pageSize, totalRows)}
            </span>{" "}
            of{" "}
            <span className="font-semibold text-ink dark:text-[#f3f4f6]">
              {totalRows}
            </span>{" "}
            entries
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              leftIcon={<IconChevronLeft className="h-3.5 w-3.5" aria-hidden="true" />}
            >
              Previous
            </Button>
            <span className="px-2">
              Page {pageIndex + 1} of {pageCount}
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              rightIcon={<IconChevronRight className="h-3.5 w-3.5" aria-hidden="true" />}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
