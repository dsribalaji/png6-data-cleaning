import { useMemo } from "react";
import { Link } from "react-router";
import type { ColumnDef } from "@tanstack/react-table";
import type { Dataset, DatasetSource } from "../../../api/schema";
import { DataTable } from "../../../shared/ui/DataTable";
import { formatDateTime, formatInt } from "../../../shared/lib/format";
import { MSG_NO_DATASETS, MSG_UPLOAD_FILE } from "../../../shared/constants/messages";
import { DATASETS_PAGE_SIZE } from "../api";
import { StatusBadge } from "./StatusBadge";

const SOURCE_LABELS: Record<DatasetSource, string> = {
  upload: MSG_UPLOAD_FILE,
  n8n_folder: "n8n folder",
};

export interface DatasetGridProps {
  datasets: Dataset[];
  loading?: boolean;
  emptyMessage?: string;
}

const columns: ColumnDef<Dataset, any>[] = [
  {
    id: "name",
    header: "Name",
    cell: ({ row }) => (
      <Link
        to={`/datasets/${row.original.id}`}
        className="font-semibold text-primary hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary rounded"
      >
        {row.original.name}
      </Link>
    ),
  },
  {
    id: "source",
    header: "Source",
    cell: ({ row }) => SOURCE_LABELS[row.original.source] ?? row.original.source,
  },
  {
    id: "rowCount",
    header: "Rows",
    meta: { align: "right" },
    cell: ({ row }) => formatInt(row.original.rowCount),
  },
  {
    id: "columnCount",
    header: "Cols",
    meta: { align: "right" },
    cell: ({ row }) => formatInt(row.original.columnCount),
  },
  {
    id: "ingestedAt",
    header: "Ingested",
    cell: ({ row }) => formatDateTime(row.original.ingestedAt),
  },
  {
    id: "status",
    header: "Status",
    cell: ({ row }) => <StatusBadge status={row.original.status} />,
  },
];

/**
 * S3 datasets grid (PRD Section 7: wireframe 1d).
 * Page size 20, newest ingest first; the Ingested column stays sortable by
 * the user on top of that default order.
 */
export function DatasetGrid({
  datasets,
  loading = false,
  emptyMessage = MSG_NO_DATASETS,
}: DatasetGridProps) {
  const sorted = useMemo(
    () =>
      [...datasets].sort((a, b) => {
        const left = new Date(a.ingestedAt).getTime();
        const right = new Date(b.ingestedAt).getTime();
        if (Number.isNaN(left) && Number.isNaN(right)) return 0;
        if (Number.isNaN(left)) return 1;
        if (Number.isNaN(right)) return -1;
        return right - left;
      }),
    [datasets]
  );

  return (
    <DataTable
      columns={columns}
      data={sorted}
      pageSize={DATASETS_PAGE_SIZE}
      loading={loading}
      emptyMessage={emptyMessage}
    />
  );
}

export default DatasetGrid;
