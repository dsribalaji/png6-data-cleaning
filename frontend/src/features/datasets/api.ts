import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import type {
  ColumnProfile,
  Dataset,
  DatasetDetail,
  DatasetProfile,
  DatasetSource,
  DatasetStatus,
  InferredRule,
  Job,
  Page,
  QuarantineRecord,
  UploadConfig,
} from "../../api/schema";
import {
  MSG_DATASET_NAME_TAKEN,
  MSG_UNSUPPORTED_FILE_TYPE,
  fileTooLarge,
} from "../../shared/constants/messages";

/**
 * S3 (datasets list) and S4 (dataset profile) server state.
 * Thin, typed layer over the ky client: every hook returns data only, the
 * components own no server state of their own (PRD Section 5).
 */

/** Alias for the PRD "quarantine row" — the API model is QuarantineRecord. */
export type QuarantineRow = QuarantineRecord;
/** Alias for the PRD "inferred rule" — the API model is InferredRule. */
export type Rule = InferredRule;

export const DATASETS_PAGE_SIZE = 20;

/** AGENTS.md default until the team confirms the value (OQ-09). */
export const DEFAULT_MAX_UPLOAD_MB = 50;

/** Fallback for a problem+json body the mapping above does not recognise. */
export const UPLOAD_FAILED_MESSAGE = "The upload failed. Please try again.";

/** PRD S3 status filter list. "" means "all". */
export type DatasetStatusFilter = DatasetStatus | "";

export interface DatasetListParams {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: DatasetStatusFilter;
}

export interface QuarantineParams {
  page?: number;
  pageSize?: number;
}

export interface GeneratePlanResponse {
  planId: string;
  job?: Job;
}

export interface UploadDatasetVariables {
  /** Omitted for the n8n folder source — the file is already on the server. */
  file?: File;
  name: string;
  source: DatasetSource;
  /** Called with 0–100 while the body is sent (ky onUploadProgress). */
  onProgress?: (percent: number) => void;
}

export interface UploadFieldError {
  message: string;
  field: "name" | "file" | "form";
}

/** Error carrying a user-facing message from messages.ts plus the field it belongs to. */
export class UploadRequestError extends Error {
  readonly field: UploadFieldError["field"];
  readonly status: number | undefined;

  constructor({ message, field }: UploadFieldError, status?: number) {
    super(message);
    this.name = "UploadRequestError";
    this.field = field;
    this.status = status;
  }
}

/**
 * Query key factory. realtime.ts invalidates the `["datasets"]` prefix for
 * every SSE event, so list keys live under that prefix and everything else
 * is namespaced per dataset.
 */
export const datasetKeys = {
  all: ["datasets"] as const,
  list: (params: DatasetListParams) => ["datasets", params] as const,
  detail: (id: string) => ["dataset", id] as const,
  profile: (id: string) => ["profile", id] as const,
  rules: (id: string) => ["rules", id] as const,
  quarantine: (id: string, params: QuarantineParams) =>
    ["quarantine", id, params] as const,
  uploadConfig: ["uploadConfig"] as const,
};

function toSearchParams(params: DatasetListParams): URLSearchParams {
  const search = new URLSearchParams();
  if (params.page) search.set("page", String(params.page));
  if (params.pageSize) search.set("pageSize", String(params.pageSize));
  if (params.search) search.set("search", params.search);
  if (params.status) search.set("status", params.status);
  return search;
}

/**
 * GET /datasets — paginated, searchable, status-filterable list (PRD S3).
 * `options` is forwarded so the page can drive the conditional 5s refetch
 * while any row is still Profiling.
 */
export function useDatasets(
  params: DatasetListParams = {},
  options?: Omit<UseQueryOptions<Page<Dataset>>, "queryKey" | "queryFn">
) {
  return useQuery<Page<Dataset>>({
    queryKey: datasetKeys.list(params),
    queryFn: async () => {
      const search = toSearchParams(params).toString();
      return api.get(`datasets${search ? `?${search}` : ""}`).json<Page<Dataset>>();
    },
    placeholderData: keepPreviousData,
    ...options,
  });
}

/** GET /datasets/{id} */
export function useDataset(
  id: string | undefined,
  options?: Omit<UseQueryOptions<DatasetDetail>, "queryKey" | "queryFn">
) {
  return useQuery<DatasetDetail>({
    queryKey: datasetKeys.detail(id ?? ""),
    queryFn: () => api.get(`datasets/${id}`).json<DatasetDetail>(),
    enabled: Boolean(id),
    ...options,
  });
}

/** GET /config/upload — max file size, allowed extensions, n8n folder path. */
export function useUploadConfig() {
  return useQuery<UploadConfig>({
    queryKey: datasetKeys.uploadConfig,
    queryFn: () => api.get("config/upload").json<UploadConfig>(),
    staleTime: 5 * 60_000,
  });
}

function maxUploadMbFromCache(queryClient: QueryClient): number {
  const config = queryClient.getQueryData<UploadConfig>(datasetKeys.uploadConfig);
  return config?.maxFileSizeMb ?? DEFAULT_MAX_UPLOAD_MB;
}

/**
 * Maps a problem+json upload failure onto the messages.ts copy and the form
 * field it belongs to (PRD Section 8: ApiError is built from the `code`).
 */
export function mapUploadError(
  error: unknown,
  maxMb: number = DEFAULT_MAX_UPLOAD_MB
): UploadFieldError {
  if (error instanceof ApiError) {
    const code = error.code ?? "";

    if (code === "DATASET_NAME_TAKEN" || (error.status === 409 && !code)) {
      return { message: MSG_DATASET_NAME_TAKEN, field: "name" };
    }
    if (code === "UNSUPPORTED_FILE_TYPE" || (error.status === 400 && !code)) {
      return { message: MSG_UNSUPPORTED_FILE_TYPE, field: "file" };
    }
    if (code === "FILE_TOO_LARGE" || error.status === 413) {
      return { message: fileTooLarge(maxMb), field: "file" };
    }

    const fieldMessage = Array.isArray(error.errors)
      ? error.errors.find((entry) => entry.field === "name")?.message
      : undefined;
    if (fieldMessage) {
      return { message: fieldMessage, field: "name" };
    }

    return { message: error.detail || error.title, field: "form" };
  }

  return { message: UPLOAD_FAILED_MESSAGE, field: "form" };
}

function normalizeUploadResponse(data: unknown): DatasetDetail {
  // The API answers with the created dataset; tolerate a {dataset:{…}} envelope.
  const record = (data ?? {}) as Record<string, unknown>;
  const nested = record.dataset as Record<string, unknown> | undefined;
  const source = nested ?? record;
  return {
    ...(source as unknown as DatasetDetail),
    status: (source.status as DatasetStatus) ?? "profiling",
  };
}

/**
 * POST /datasets — multipart upload. The new row comes back with status
 * "Profiling"; the list cache is patched here so the row appears immediately,
 * then live SSE invalidations / conditional refetches keep its status fresh.
 */
export function useUploadDataset() {
  const queryClient = useQueryClient();

  return useMutation<DatasetDetail, UploadRequestError, UploadDatasetVariables>({
    mutationFn: async ({ file, name, source, onProgress }) => {
      const form = new FormData();
      if (file) {
        form.append("file", file);
      }
      form.append("name", name);
      form.append("source", source);

      try {
        // ponytail: coarse 0 → 100 progress. ky's onUploadProgress streams the body
        // (duplex "half"), which Chrome rejects over HTTP/1.1; use XHR for a real bar.
        onProgress?.(0);
        const data = await api.post("datasets", { body: form }).json<unknown>();
        onProgress?.(100);
        return normalizeUploadResponse(data);
      } catch (error) {
        const maxMb = maxUploadMbFromCache(queryClient);
        const mapped = mapUploadError(error, maxMb);
        throw new UploadRequestError(
          mapped,
          error instanceof ApiError ? error.status : undefined
        );
      }
    },
    onSuccess: (created) => {
      if (!created.id) {
        // Nothing usable came back — fall back to a plain list refresh.
        queryClient.invalidateQueries({ queryKey: datasetKeys.all });
        return;
      }
      queryClient.setQueryData(datasetKeys.detail(created.id), created);
      prependToDatasetLists(queryClient, created);
    },
  });
}

/**
 * Prepends the freshly created dataset to every cached `["datasets", params]`
 * page so the S3 grid shows it without a round trip (PRD S3: "prepends the row
 * with status Profiling").
 */
export function prependToDatasetLists(
  queryClient: QueryClient,
  dataset: Dataset
): void {
  const listQueries = queryClient.getQueryCache().findAll({
    queryKey: datasetKeys.all,
  });

  for (const query of listQueries) {
    const key = query.queryKey;
    // `findAll` also matches `["datasets", id]`; only patch the paged lists.
    if (key.length !== 2) continue;

    queryClient.setQueryData<Page<Dataset>>(key, (previous) => {
      if (!previous || !Array.isArray(previous.items)) return previous;
      if (previous.items.some((item) => item.id === dataset.id)) return previous;
      return {
        ...previous,
        items: [dataset, ...previous.items],
        total: previous.total + 1,
      };
    });
  }
}

/** GET /datasets/{id}/quarantine — paginated quarantined rows with reasons. */
export function useQuarantine(
  id: string | undefined,
  params: QuarantineParams = {}
) {
  return useQuery<Page<QuarantineRow>>({
    queryKey: datasetKeys.quarantine(id ?? "", params),
    queryFn: async () => {
      const search = new URLSearchParams();
      if (params.page) search.set("page", String(params.page));
      if (params.pageSize) search.set("pageSize", String(params.pageSize));
      const query = search.toString();
      return api
        .get(`datasets/${id}/quarantine${query ? `?${query}` : ""}`)
        .json<Page<QuarantineRow>>();
    },
    enabled: Boolean(id),
    placeholderData: keepPreviousData,
  });
}

/** GET /datasets/{id}/profile — column profiles plus the KPI summary. */
export function useProfile(
  id: string | undefined,
  options?: Omit<UseQueryOptions<DatasetProfile>, "queryKey" | "queryFn">
) {
  return useQuery<DatasetProfile>({
    queryKey: datasetKeys.profile(id ?? ""),
    queryFn: async () => toDatasetProfile(await api.get(`datasets/${id}/profile`).json<RawProfile>()),
    enabled: Boolean(id),
    ...options,
  });
}

/** GET /datasets/{id}/profile as the API sends it. */
interface RawProfile {
  datasetId: string;
  rowCount: number;
  columnCount: number;
  quarantinedRowsCount?: number;
  columns: Array<Omit<ColumnProfile, "columnName" | "id" | "datasetId"> & { name: string }>;
}

/** API → view model: column names, null share 0–1 → percent, summary KPIs derived. */
export function toDatasetProfile(raw: RawProfile): DatasetProfile {
  const columns: ColumnProfile[] = raw.columns.map((c) => ({
    ...c,
    id: `${raw.datasetId}:${c.name}`,
    datasetId: raw.datasetId,
    columnName: c.name,
    nullPct: c.nullPct * 100,
    flags: c.flags ?? [],
  }));
  return {
    datasetId: raw.datasetId,
    columns,
    summary: {
      rowCount: raw.rowCount,
      columnCount: raw.columnCount,
      columnsWithNullsCount: columns.filter((c) => c.nullCount > 0).length,
      nestedColumnsCount: columns.filter(
        (c) => c.semanticType === "nested_json" || c.flags.includes("nested_json")
      ).length,
      quarantinedRowsCount: raw.quarantinedRowsCount ?? 0,
    },
  };
}

/** GET /datasets/{id}/rules — rules inferred from the profiled data. */
export function useRules(
  id: string | undefined,
  options?: Omit<UseQueryOptions<Rule[]>, "queryKey" | "queryFn">
) {
  return useQuery<Rule[]>({
    queryKey: datasetKeys.rules(id ?? ""),
    queryFn: () => api.get(`datasets/${id}/rules`).json<Rule[]>(),
    enabled: Boolean(id),
    ...options,
  });
}

/** POST /datasets/{id}/plans — starts plan generation (the SSE event finishes it). */
export function useGeneratePlan() {
  const queryClient = useQueryClient();

  return useMutation<GeneratePlanResponse, Error, { id: string; lossThreshold?: number }>({
    mutationFn: async ({ id, lossThreshold }) =>
      api
        .post(`datasets/${id}/plans`, {
          json: lossThreshold === undefined ? {} : { lossThreshold },
        })
        .json<GeneratePlanResponse & { id?: string; steps?: unknown[] }>()
        // The API answers with the plan itself; eager/local mode already includes its steps.
        .then((plan) => ({ ...plan, planId: plan.planId ?? plan.id, stepCount: plan.steps?.length ?? 0 })),
    onSuccess: (data) => {
      if (data.planId) {
        queryClient.invalidateQueries({ queryKey: ["plans", data.planId] });
      }
    },
  });
}
