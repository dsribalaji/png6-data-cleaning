import { useState, useCallback } from "react";

export interface UsePaginationOptions {
  initialPage?: number;
  initialPageSize?: number;
  total?: number;
}

export interface UsePaginationResult {
  page: number;
  pageSize: number;
  setPage: (page: number | ((prev: number) => number)) => void;
  setPageSize: (pageSize: number) => void;
  nextPage: () => void;
  prevPage: () => void;
  goToPage: (page: number) => void;
  reset: () => void;
  totalPages: number;
  hasNextPage: boolean;
  hasPrevPage: boolean;
}

/**
 * Standard client/server pagination state management hook.
 */
export function usePagination(options: UsePaginationOptions = {}): UsePaginationResult {
  const { initialPage = 1, initialPageSize = 20, total = 0 } = options;
  const [page, setPage] = useState<number>(initialPage);
  const [pageSize, setPageSize] = useState<number>(initialPageSize);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const nextPage = useCallback(() => {
    setPage((p) => Math.min(totalPages, p + 1));
  }, [totalPages]);

  const prevPage = useCallback(() => {
    setPage((p) => Math.max(1, p - 1));
  }, []);

  const goToPage = useCallback(
    (newPage: number) => {
      setPage(Math.max(1, Math.min(totalPages, newPage)));
    },
    [totalPages]
  );

  const reset = useCallback(() => {
    setPage(1);
  }, []);

  return {
    page,
    pageSize,
    setPage,
    setPageSize,
    nextPage,
    prevPage,
    goToPage,
    reset,
    totalPages,
    hasNextPage: page < totalPages,
    hasPrevPage: page > 1,
  };
}
