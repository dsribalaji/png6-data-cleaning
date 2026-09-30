import {
  keepPreviousData,
  useMutation,
  useQuery,
  type UseMutationResult,
  type UseQueryOptions,
  type UseQueryResult,
} from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import type { AuditEvent, Page } from "../../api/schema";
import type { Permission } from "../../auth/permissions";
import { downloadFromUrl } from "../../shared/lib/download";
import {
  MSG_END_DATE_AFTER_START,
  MSG_EXPORT_FAILED,
} from "../../shared/constants/messages";

/**
 * S9 Audit trail server state (PRD Section 7, wireframe 1l).
 *
 * The event vocabulary is static — it is the contract the backend writes to —
 * so it lives here as a literal list rather than being fetched.
 */

export const AUDIT_PAGE_SIZE = 50;

export const AUDIT_EVENT_TYPES = [
  "login",
  "logout",
  "dataset.upload",
  "plan.approve",
  "plan.execute",
  "validation.completed",
  "export",
  "rollback",
  "user.invite",
  "model.update",
] as const;

export type AuditEventType = (typeof AUDIT_EVENT_TYPES)[number];

/** True when the backend recorded an event type the UI does not list yet. */
export function isKnownAuditEventType(value: string): value is AuditEventType {
  return (AUDIT_EVENT_TYPES as readonly string[]).includes(value);
}

export interface AuditFiltersState {
  /** ISO date (yyyy-MM-dd) inclusive lower bound, in UTC. */
  fromDate?: string;
  /** ISO date (yyyy-MM-dd) inclusive upper bound, in UTC. */
  toDate?: string;
  eventTypes: string[];
  userId?: string;
}

export const EMPTY_AUDIT_FILTERS: AuditFiltersState = { eventTypes: [] };

export const auditKeys = {
  all: ["auditEvents"] as const,
  list: (filters: AuditEventsParams) => ["auditEvents", filters] as const,
};

export interface AuditEventsParams {
  from?: string;
  to?: string;
  eventTypes?: string[];
  userId?: string;
  page?: number;
  pageSize?: number;
}

function toSearchParams(params: AuditEventsParams): URLSearchParams {
  const search = new URLSearchParams();
  if (params.from) search.set("fromDate", params.from);
  if (params.to) search.set("toDate", params.to);
  if (params.eventTypes && params.eventTypes.length > 0) {
    // Repeated key: the backend reads a list of event types.
    for (const eventType of params.eventTypes) search.append("eventType", eventType);
  }
  if (params.userId) search.set("userId", params.userId);
  if (params.page) search.set("page", String(params.page));
  if (params.pageSize) search.set("pageSize", String(params.pageSize));
  return search;
}

/**
 * To >= From (PRD S9). An empty bound is ignored, so a single-sided range is
 * always valid.
 */
export function isAuditRangeValid(filters: AuditFiltersState): boolean {
  const { fromDate, toDate } = filters;
  if (!fromDate || !toDate) return true;
  return toDate >= fromDate;
}

export function auditRangeError(filters: AuditFiltersState): string | null {
  return isAuditRangeValid(filters) ? null : MSG_END_DATE_AFTER_START;
}

/** Newest first (PRD S9: Timestamp UTC, sort desc). */
export function sortAuditEventsDesc(events: AuditEvent[]): AuditEvent[] {
  return [...events].sort((a, b) => {
    const left = new Date(a.occurredAt).getTime();
    const right = new Date(b.occurredAt).getTime();
    if (Number.isNaN(left) && Number.isNaN(right)) return 0;
    if (Number.isNaN(left)) return 1;
    if (Number.isNaN(right)) return -1;
    return right - left;
  });
}

export interface AuditObjectTarget {
  to: string;
  /** The permission needed to open the target, so links stay hidden for roles
   *  that would only get a 403 page. */
  perm: Permission;
}

/**
 * Where an audit row's object lives. Objects with no screen of their own (a
 * login, a logout) have no target and render as plain text.
 */
export function auditObjectTarget(event: AuditEvent): AuditObjectTarget | null {
  const type = (event.objectType ?? "").toLowerCase();
  const id = event.objectId;

  switch (type) {
    case "dataset":
      return { to: `/datasets/${id}`, perm: "profile.view" };
    case "plan":
    case "job":
    case "export":
    case "rollback":
    case "validation":
      return { to: `/plans/${id}`, perm: "profile.view" };
    case "user":
    case "invite":
      return { to: "/settings/users", perm: "users.view" };
    case "model":
    case "model_config":
    case "model-config":
      return { to: "/settings/model", perm: "model.view" };
    case "evaluation":
      return { to: "/evaluation", perm: "evaluation.run" };
    default:
      return null;
  }
}

/** GET /audit-events — filtered, newest first, 50 per page (PRD S9). */
export function useAuditEvents(
  params: AuditEventsParams = {},
  options?: Omit<UseQueryOptions<Page<AuditEvent>, ApiError>, "queryKey" | "queryFn">
): UseQueryResult<Page<AuditEvent>, ApiError> {
  return useQuery<Page<AuditEvent>, ApiError>({
    queryKey: auditKeys.list(params),
    queryFn: () => {
      const search = toSearchParams(params).toString();
      return api
        .get(`audit-events${search ? `?${search}` : ""}`)
        .json<Page<AuditEvent>>();
    },
    placeholderData: keepPreviousData,
    ...options,
  });
}

/** Filename for the CSV download of the current filter result. */
export function auditExportFileName(filters: AuditFiltersState): string {
  const from = filters.fromDate ?? "all";
  const to = filters.toDate ?? "all";
  return `audit-events_${from}_${to}.csv`;
}

export type UseAuditExportResult = UseMutationResult<
  string,
  ApiError,
  AuditFiltersState
>;

/**
 * GET /audit-events/export, then download the CSV (Auditor only).
 *
 * The endpoint is expected to answer with a pre-signed `downloadUrl`, matching
 * every other export in the API. If it instead streams the file itself, the
 * endpoint URL is downloaded directly — `downloadFromUrl` attaches the Bearer
 * header and saves the blob either way.
 */
export function useAuditExport(): UseAuditExportResult {
  return useMutation<string, ApiError, AuditFiltersState>({
    mutationFn: async (filters) => {
      const search = toSearchParams({
        from: filters.fromDate,
        to: filters.toDate,
        eventTypes: filters.eventTypes,
        userId: filters.userId,
      }).toString();

      const path = `audit-events/export${search ? `?${search}` : ""}`;
      const filename = auditExportFileName(filters);

      let downloadUrl = `/api/v1/${path}`;

      try {
        const payload = (await api.get(path).json<unknown>()) as
          | { downloadUrl?: unknown }
          | null;
        if (payload && typeof payload.downloadUrl === "string" && payload.downloadUrl) {
          downloadUrl = payload.downloadUrl;
        }
      } catch (error) {
        // A streamed CSV is a non-JSON 200 body, so a parse failure simply
        // means there is no pre-signed URL to use. A real failure aborts.
        if (error instanceof ApiError) throw error;
      }

      try {
        await downloadFromUrl(downloadUrl, filename);
      } catch {
        throw new ApiError({
          title: MSG_EXPORT_FAILED,
          status: 500,
          detail: MSG_EXPORT_FAILED,
        });
      }

      return filename;
    },
  });
}
