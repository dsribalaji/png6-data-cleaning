import { useEffect, useMemo, useState } from "react";
import { IconDatabase, IconSearch, IconUpload } from "@tabler/icons-react";
import { Can } from "../../../auth/Can";
import { ApiError } from "../../../api/client";
import { Button } from "../../../shared/ui/Button";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { Input } from "../../../shared/ui/Input";
import { Select } from "../../../shared/ui/Select";
import { Skeleton } from "../../../shared/ui/Skeleton";
import { useDebounce } from "../../../shared/hooks/useDebounce";
import { formatInt } from "../../../shared/lib/format";
import { MSG_DATASETS_LOAD_FAILED, MSG_NO_DATASETS, MSG_NO_DATASETS_MATCH } from "../../../shared/constants/messages";
import type { DatasetStatus } from "../../../api/schema";
import {
  DATASETS_PAGE_SIZE,
  useDatasets,
  type DatasetStatusFilter,
} from "../api";
import {
  DATASET_STATUS_LABEL,
  DATASET_STATUS_OPTIONS,
} from "../components/StatusBadge";
import { DatasetGrid } from "../components/DatasetGrid";
import { UploadDatasetModal } from "../components/UploadDatasetModal";

const ALL_STATUSES_LABEL = "All statuses";
const SEARCH_LABEL = "Search by name";
const STATUS_FILTER_LABEL = "Filter by status";
const REFRESH_WHILE_PROFILING_MS = 5000;

/** ApiError carries the problem+json detail; anything else falls back. */
function loadErrorMessage(error: Error | null): string {
  if (error instanceof ApiError) {
    return error.detail || error.title || MSG_DATASETS_LOAD_FAILED;
  }
  return MSG_DATASETS_LOAD_FAILED;
}

/**
 * S3 Datasets (PRD Section 7, wireframe 1d).
 * Server-side paging, search debounced 300 ms, status filter, and a 5 s
 * refetch only while a row is still Profiling. SSE streams are per dataset, so
 * list freshness comes from the invalidations realtime.ts fires for any open
 * stream plus this conditional polling window.
 */
export function DatasetsPage() {
  const [searchInput, setSearchInput] = useState("");
  const [status, setStatus] = useState<DatasetStatusFilter>("");
  const [page, setPage] = useState(1);
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  const search = useDebounce(searchInput, 300);

  const { data, isPending, isFetching, isError, error } = useDatasets(
    { page, pageSize: DATASETS_PAGE_SIZE, search, status },
    {
      // Conditional refetch: only while something is still being profiled.
      refetchInterval: (query) => {
        const items = query.state.data?.items;
        if (!items || items.length === 0) return false;
        return items.some((item) => item.status === "profiling")
          ? REFRESH_WHILE_PROFILING_MS
          : false;
      },
    }
  );

  const total = data?.total ?? 0;
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / DATASETS_PAGE_SIZE)),
    [total]
  );
  const isProfiling = useMemo(
    () => (data?.items ?? []).some((item) => item.status === "profiling"),
    [data?.items]
  );

  // A new search or filter always restarts at the first page.
  useEffect(() => {
    setPage(1);
  }, [search, status]);

  // Keep the pager inside the result set when a page becomes unreachable.
  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const showSkeleton = isPending && !data;
  const showEmpty = !isPending && !isError && (data?.items.length ?? 0) === 0;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[#1f2937] dark:text-[#f3f4f6]">
            Datasets
          </h1>
          <p className="mt-0.5 text-sm text-[#6c757d] dark:text-[#a0aec0]">
            Upload a file or connect the n8n output folder to start profiling.
          </p>
        </div>
        <Can perm="dataset.upload">
          <Button
            leftIcon={<IconUpload className="h-4 w-4" aria-hidden="true" />}
            onClick={() => setIsUploadOpen(true)}
          >
            Upload dataset
          </Button>
        </Can>
      </header>

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-full max-w-xs">
          <Input
            type="search"
            label={SEARCH_LABEL}
            value={searchInput}
            placeholder="Search datasets…"
            autoComplete="off"
            onChange={(event) => setSearchInput(event.target.value)}
            leftIcon={<IconSearch className="h-4 w-4" aria-hidden="true" />}
          />
        </div>
        <div className="w-full max-w-[14rem]">
          <Select
            label={STATUS_FILTER_LABEL}
            value={status}
            onChange={(event) => setStatus(event.target.value as DatasetStatusFilter)}
            options={[
              { value: "", label: ALL_STATUSES_LABEL },
              ...DATASET_STATUS_OPTIONS.map((value: DatasetStatus) => ({
                value,
                label: DATASET_STATUS_LABEL[value],
              })),
            ]}
          />
        </div>
      </div>

      {isError && (
        <div
          role="alert"
          className="rounded-md border border-[#f5c6cb] bg-[#f8d7da] px-4 py-3 text-sm text-[#721c24] dark:border-[#662025] dark:bg-[#3d1a1c] dark:text-[#f5a3a9]"
        >
          {loadErrorMessage(error)}
        </div>
      )}

      {showSkeleton ? (
        <div className="space-y-3" role="status" aria-label="Loading datasets…">
          <Skeleton className="h-12 w-full rounded-lg" />
          <Skeleton className="h-64 w-full rounded-lg" />
        </div>
      ) : showEmpty ? (
        <EmptyState
          icon={<IconDatabase className="h-6 w-6 stroke-[1.5]" aria-hidden="true" />}
          message={search || status ? MSG_NO_DATASETS_MATCH : MSG_NO_DATASETS}
        />
      ) : (
        <>
          <DatasetGrid
            datasets={data?.items ?? []}
            loading={isFetching && !isPending}
          />

          <nav
            aria-label="Datasets pagination"
            className="flex flex-wrap items-center justify-between gap-3 text-xs text-[#6c757d] dark:text-[#a0aec0]"
          >
            <span>
              {formatInt(total)} dataset{total === 1 ? "" : "s"}
              {isProfiling ? " · profiling in progress" : ""}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={page <= 1 || isFetching}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                Previous
              </Button>
              <span className="px-1 tabular-nums">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={page >= totalPages || isFetching}
                onClick={() => setPage((current) => current + 1)}
              >
                Next
              </Button>
            </div>
          </nav>
        </>
      )}

      <UploadDatasetModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
      />
    </div>
  );
}

export default DatasetsPage;
