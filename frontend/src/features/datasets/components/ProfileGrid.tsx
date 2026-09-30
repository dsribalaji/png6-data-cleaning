import { useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { IconChevronDown, IconChevronRight } from "@tabler/icons-react";
import type { ColumnProfile } from "../../../api/schema";
import { Badge } from "../../../shared/ui/Badge";
import { DataTable } from "../../../shared/ui/DataTable";
import { formatInt, formatPct } from "../../../shared/lib/format";

const COLUMN_LABEL = "Column";
const PHYSICAL_TYPE_LABEL = "Physical type";
const SEMANTIC_TYPE_LABEL = "Semantic type";
const NULL_PCT_LABEL = "Null %";
const DISTINCT_LABEL = "Distinct";
const FLAGS_LABEL = "Flags";
const NO_PROFILE_COLUMNS = "This dataset has no columns yet.";
const NO_FLAGS = "No flags";

export interface ProfileGridProps {
  columns: ColumnProfile[];
  loading?: boolean;
}

function isBlank(value: string | number | null | undefined): boolean {
  return value === null || value === undefined || value === "";
}

function DetailItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-[#6c757d] dark:text-[#a0aec0]">
        {label}
      </span>
      <span className="text-sm text-[#1f2937] dark:text-[#f3f4f6] break-all">
        {value}
      </span>
    </div>
  );
}

/**
 * S4 profile grid (PRD Section 7, wireframe 1e).
 * Numbers right-aligned, null % at 0 decimal places, flags as danger pills.
 * Clicking a row expands min / max / mean beneath the column name.
 */
export function ProfileGrid({ columns, loading = false }: ProfileGridProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggle = (id: string) =>
    setExpandedId((current) => (current === id ? null : id));

  const tableColumns: ColumnDef<ColumnProfile, any>[] = [
    {
      id: "columnName",
      header: COLUMN_LABEL,
      cell: ({ row }) => {
        const isExpanded = expandedId === row.original.id;
        return (
          <div className="text-left">
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                toggle(row.original.id);
              }}
              aria-expanded={isExpanded}
              className="inline-flex max-w-full items-center gap-1.5 rounded text-left font-semibold text-[#1f2937] dark:text-[#f3f4f6] hover:text-[#fd6321] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#fd6321]"
            >
              {isExpanded ? (
                <IconChevronDown className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
              ) : (
                <IconChevronRight className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
              )}
              <span className="truncate">{row.original.columnName}</span>
            </button>

            {isExpanded && (
              <div className="mt-2 grid grid-cols-1 gap-2 rounded-md border border-[#e9ecef] dark:border-[#343a40] bg-[#f8f9fa] dark:bg-[#1f2327] p-3 sm:grid-cols-3">
                <DetailItem
                  label="Min"
                  value={
                    isBlank(row.original.minValue)
                      ? "—"
                      : String(row.original.minValue)
                  }
                />
                <DetailItem
                  label="Max"
                  value={
                    isBlank(row.original.maxValue)
                      ? "—"
                      : String(row.original.maxValue)
                  }
                />
                <DetailItem
                  label="Mean"
                  value={
                    isBlank(row.original.meanValue)
                      ? "—"
                      : Number(row.original.meanValue).toFixed(2)
                  }
                />
              </div>
            )}
          </div>
        );
      },
    },
    {
      id: "physicalType",
      header: PHYSICAL_TYPE_LABEL,
      cell: ({ row }) => (
        <span className="text-xs text-[#6c757d] dark:text-[#a0aec0]">
          {row.original.physicalType}
        </span>
      ),
    },
    {
      id: "semanticType",
      header: SEMANTIC_TYPE_LABEL,
      cell: ({ row }) => (
        <span className="text-xs font-medium text-[#1f2937] dark:text-[#f3f4f6]">
          {row.original.semanticType}
        </span>
      ),
    },
    {
      id: "nullPct",
      header: NULL_PCT_LABEL,
      meta: { align: "right" },
      cell: ({ row }) => formatPct(row.original.nullPct, 0),
    },
    {
      id: "distinctCount",
      header: DISTINCT_LABEL,
      meta: { align: "right" },
      cell: ({ row }) => formatInt(row.original.distinctCount),
    },
    {
      id: "flags",
      header: FLAGS_LABEL,
      cell: ({ row }) => {
        const flags = row.original.flags ?? [];
        if (flags.length === 0) {
          return (
            <span className="text-xs text-[#6c757d] dark:text-[#a0aec0]">{NO_FLAGS}</span>
          );
        }
        return (
          <span className="flex flex-wrap justify-end gap-1.5">
            {flags.map((flag) => (
              <Badge key={flag} variant="danger">
                {flag}
              </Badge>
            ))}
          </span>
        );
      },
    },
  ];

  return (
    <DataTable
      columns={tableColumns}
      data={columns}
      pageSize={20}
      loading={loading}
      emptyMessage={NO_PROFILE_COLUMNS}
      onRowClick={(row) => toggle(row.id)}
    />
  );
}

export default ProfileGrid;
