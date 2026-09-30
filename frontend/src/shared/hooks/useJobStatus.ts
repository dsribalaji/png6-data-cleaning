import { useQueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import type { Dataset, DatasetDetail, DatasetStatus, Page } from "../../api/schema";

export interface JobStatusInfo {
  status: DatasetStatus | undefined;
  dataset: Dataset | DatasetDetail | undefined;
  isProfiling: boolean;
  isPlanReady: boolean;
  isApproved: boolean;
  isExecuted: boolean;
  isFailed: boolean;
  isRolledBack: boolean;
}

/**
 * Reads the datasets query cache and returns the latest job / dataset status
 * without any polling, keeping the UI fully reactive to SSE cache invalidations.
 */
export function useJobStatus(datasetId: string | undefined): JobStatusInfo {
  const queryClient = useQueryClient();

  const getSnapshot = (): {
    status: DatasetStatus | undefined;
    dataset: Dataset | DatasetDetail | undefined;
  } => {
    if (!datasetId) {
      return { status: undefined, dataset: undefined };
    }

    // 1. Check specific single dataset query: ["datasets", datasetId]
    const singleData = queryClient.getQueryData<DatasetDetail | Dataset>([
      "datasets",
      datasetId,
    ]);
    if (singleData) {
      return { status: singleData.status, dataset: singleData };
    }

    // 2. Check dataset list queries: ["datasets"]
    const queries = queryClient.getQueryCache().findAll({ queryKey: ["datasets"] });
    for (const query of queries) {
      const data = query.state.data as Page<Dataset> | Dataset[] | undefined;
      if (!data) continue;
      const items = Array.isArray(data) ? data : data.items;
      if (Array.isArray(items)) {
        const match = items.find((item) => item.id === datasetId);
        if (match) {
          return { status: match.status, dataset: match };
        }
      }
    }

    return { status: undefined, dataset: undefined };
  };

  // We serialize snapshot identity or compare to prevent re-renders when data hasn't changed
  const subscribe = (callback: () => void) => {
    return queryClient.getQueryCache().subscribe(callback);
  };

  // Read current snapshot
  const data = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const status = data.status;

  return {
    status,
    dataset: data.dataset,
    isProfiling: status === "profiling",
    isPlanReady: status === "plan_ready",
    isApproved: status === "approved",
    isExecuted: status === "executed",
    isFailed: status === "failed" || status === "tests_failed",
    isRolledBack: status === "rolled_back",
  };
}
