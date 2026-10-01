import { useCallback, useMemo } from "react";
import { Link, useSearchParams } from "react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { IconDownload, IconExternalLink, IconListCheck } from "@tabler/icons-react";
import { motion, useReducedMotion } from "motion/react";
import { Can } from "../../../auth/Can";
import { usePermission, type Permission } from "../../../auth/permissions";
import { ApiError } from "../../../api/client";
import type { AuditEvent, Page } from "../../../api/schema";
import { Badge } from "../../../shared/ui/Badge";
import { Button } from "../../../shared/ui/Button";
import { DataTable } from "../../../shared/ui/DataTable";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { useToast } from "../../../shared/ui/Toast";
import { formatInt, formatUtc } from "../../../shared/lib/format";
import {
  MSG_AUDIT_LOAD_FAILED,
  MSG_AUDIT_SUBTITLE,
  MSG_AUDIT_TITLE,
  MSG_EVENT,
  MSG_EVENTS_COUNT,
  MSG_EXPORT_CSV,
  MSG_EXPORT_CSV_READY,
  MSG_EXPORT_FAILED,
  MSG_EXPORTING_CSV,
  MSG_LOADING,
  MSG_NEXT,
  MSG_NO_EVENTS_MATCH,
  MSG_OBJECT,
  MSG_PAGE_OF,
  MSG_PREVIOUS,
  MSG_ROLE,
  MSG_TIMESTAMP_UTC,
  MSG_USER,
} from "../../../shared/constants/messages";
import { ROLE_LABELS } from "../../users/schemas";
import { USER_OPTION_LIMIT, useUsers } from "../../users/api";
import { AuditFilters } from "../components/AuditFilters";
import {
  AUDIT_PAGE_SIZE,
  auditObjectTarget,
  auditRangeError,
  isAuditRangeValid,
  sortAuditEventsDesc,
  useAuditEvents,
  useAuditExport,
  type AuditFiltersState,
} from "../api";

/**
 * S9 Audit trail (PRD Section 7, wireframe 1l, preview.html spec).
 *
 * Read-only. Every filter is mirrored into the query string, the newest event is
 * listed first, and only roles holding `audit.export` see the export control.
 */
export function AuditPage() {
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const shouldReduceMotion = useReducedMotion();

  const canFilterByUser = usePermission("users.view");

  // Hooks are unconditional; the permission decides whether the request fires.
  const canViewProfile = usePermission("profile.view");
  const canViewModel = usePermission("model.view");
  const canRunEvaluation = usePermission("evaluation.run");

  const filters = useMemo<AuditFiltersState>(
    () => ({
      fromDate: searchParams.get("from") || undefined,
      toDate: searchParams.get("to") || undefined,
      eventTypes: searchParams.getAll("eventType"),
      userId: searchParams.get("userId") || undefined,
    }),
    [searchParams]
  );

  const page = useMemo(() => {
    const raw = Number(searchParams.get("page") ?? "1");
    return Number.isFinite(raw) && raw >= 1 ? Math.floor(raw) : 1;
  }, [searchParams]);

  const rangeError = auditRangeError(filters);
  const isRangeValid = isAuditRangeValid(filters);

  const eventsQuery = useAuditEvents(
    {
      from: filters.fromDate,
      to: filters.toDate,
      eventTypes: filters.eventTypes.length > 0 ? filters.eventTypes : undefined,
      userId: filters.userId,
      page,
      pageSize: AUDIT_PAGE_SIZE,
    },
    // An impossible range is reported in the form; it is never sent.
    { enabled: isRangeValid }
  );

  // `GET /users` needs users.view, which an Auditor does not hold, so the
  // request is gated rather than left to 403.
  const usersQuery = useUsers(
    { page: 1, pageSize: USER_OPTION_LIMIT },
    { enabled: canFilterByUser }
  );

  const exportMutation = useAuditExport();

  const applyFilters = useCallback(
    (next: AuditFiltersState) => {
      const params = new URLSearchParams();
      if (next.fromDate) params.set("from", next.fromDate);
      if (next.toDate) params.set("to", next.toDate);
      for (const eventType of next.eventTypes) params.append("eventType", eventType);
      if (next.userId) params.set("userId", next.userId);
      setSearchParams(params, { replace: true });
    },
    [setSearchParams]
  );

  const goToPage = useCallback(
    (next: number) => {
      const params = new URLSearchParams();
      if (filters.fromDate) params.set("from", filters.fromDate);
      if (filters.toDate) params.set("to", filters.toDate);
      for (const eventType of filters.eventTypes) params.append("eventType", eventType);
      if (filters.userId) params.set("userId", filters.userId);
      const targetPage = Math.max(1, next);
      if (targetPage > 1) params.set("page", String(targetPage));
      setSearchParams(params);
    },
    [filters, setSearchParams]
  );

  const allowedPerms = useMemo<Partial<Record<Permission, boolean>>>(
    () => ({
      "profile.view": canViewProfile,
      "users.view": canFilterByUser,
      "model.view": canViewModel,
      "evaluation.run": canRunEvaluation,
    }),
    [canViewProfile, canFilterByUser, canViewModel, canRunEvaluation]
  );

  const columns = useMemo<ColumnDef<AuditEvent, any>[]>(
    () => [
      {
        id: "occurredAt",
        header: MSG_TIMESTAMP_UTC,
        accessorFn: (row) => row.occurredAt,
        cell: ({ row }) => (
          <span className="whitespace-nowrap tabular-nums text-ink2 text-xs">
            {formatUtc(row.original.occurredAt)}
          </span>
        ),
      },
      {
        id: "user",
        header: MSG_USER,
        accessorFn: (row) => row.userEmail ?? "",
        cell: ({ row }) =>
          row.original.userEmail ? (
            <span className="font-medium text-ink">{row.original.userEmail}</span>
          ) : (
            <span className="text-ink2">—</span>
          ),
      },
      {
        id: "role",
        header: MSG_ROLE,
        accessorFn: (row) => ROLE_LABELS[row.userRole] ?? row.userRole,
        cell: ({ row }) => (
          <Badge variant="secondary">
            {ROLE_LABELS[row.original.userRole] ?? row.original.userRole}
          </Badge>
        ),
      },
      {
        id: "eventType",
        header: MSG_EVENT,
        accessorFn: (row) => row.eventType,
        cell: ({ row }) => (
          <kbd className="inline-block rounded border border-line bg-canvas px-2 py-0.5 font-mono text-xs font-medium text-ink2">
            {row.original.eventType}
          </kbd>
        ),
      },
      {
        id: "object",
        header: MSG_OBJECT,
        accessorFn: (row) => row.objectId,
        cell: ({ row }) => {
          const { objectType, objectId } = row.original;
          const target = auditObjectTarget(row.original);

          if (target === null || allowedPerms[target.perm] !== true) {
            return (
              <span className="font-mono text-xs text-ink">
                {objectId}{" "}
                <span className="font-sans text-ink2">
                  ({objectType})
                </span>
              </span>
            );
          }

          return (
            <Link
              to={target.to}
              className="inline-flex items-center gap-1.5 font-mono text-xs text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              {objectId}{" "}
              <span className="font-sans text-ink2">
                ({objectType})
              </span>
              <IconExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          );
        },
      },
    ],
    [allowedPerms]
  );

  const pageData: Page<AuditEvent> | undefined = eventsQuery.data;
  const events = useMemo(
    () => sortAuditEventsDesc(pageData?.items ?? []),
    [pageData?.items]
  );
  const total = pageData?.total ?? 0;
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / AUDIT_PAGE_SIZE)),
    [total]
  );

  const handleExport = () => {
    if (!isRangeValid) return;
    exportMutation.mutate(filters, {
      onSuccess: () => toast.success(MSG_EXPORT_CSV_READY),
      onError: (error) =>
        toast.error(
          error instanceof ApiError
            ? error.detail || error.title || MSG_EXPORT_FAILED
            : MSG_EXPORT_FAILED
        ),
    });
  };

  const showSkeleton = eventsQuery.isPending && !eventsQuery.data;
  const showEmpty =
    !eventsQuery.isPending && !eventsQuery.isError && events.length === 0 && isRangeValid;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-ink">
            {MSG_AUDIT_TITLE}
          </h1>
          <p className="mt-0.5 text-sm text-ink2">
            {MSG_AUDIT_SUBTITLE}
          </p>
        </div>
        <div>
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-ink2">
            Read-only
          </span>
        </div>
      </header>

      <AuditFilters
        filters={filters}
        onChange={applyFilters}
        onClear={() => applyFilters({ eventTypes: [] })}
        users={canFilterByUser ? (usersQuery.data?.items ?? []) : []}
        usersLoading={canFilterByUser && usersQuery.isPending}
        canFilterByUser={canFilterByUser}
        disabled={!isRangeValid}
        isExporting={exportMutation.isPending}
        exportAction={
          <Can perm="audit.export">
            <Button
              leftIcon={<IconDownload className="h-4 w-4" aria-hidden="true" />}
              onClick={handleExport}
              disabled={!isRangeValid || exportMutation.isPending}
            >
              {exportMutation.isPending ? MSG_EXPORTING_CSV : MSG_EXPORT_CSV}
            </Button>
          </Can>
        }
      />

      {eventsQuery.isError && (
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-danger"
        >
          {eventsQuery.error?.detail ||
            eventsQuery.error?.title ||
            MSG_AUDIT_LOAD_FAILED}
        </div>
      )}

      {!isRangeValid && rangeError && (
        <p
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-danger"
        >
          {rangeError}
        </p>
      )}

      {showSkeleton ? (
        <div role="status" aria-label={MSG_LOADING(MSG_AUDIT_TITLE)} className="space-y-3">
          <div className="h-12 w-full rounded-lg bg-slate-100 animate-pulse dark:bg-slate-800" />
          <div className="h-72 w-full rounded-lg bg-slate-100 animate-pulse dark:bg-slate-800" />
        </div>
      ) : showEmpty ? (
        <EmptyState
          icon={<IconListCheck className="h-6 w-6 stroke-[1.5]" aria-hidden="true" />}
          message={MSG_NO_EVENTS_MATCH}
        />
      ) : isRangeValid ? (
        <motion.div
          whileHover={shouldReduceMotion ? undefined : { y: -1 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="card rounded-[10px] border border-line bg-surface p-5 shadow-sm"
        >
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-ink">Log entries</h2>
            <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-ink2">
              {MSG_EVENTS_COUNT(formatInt(total))}
            </span>
          </div>

          <DataTable
            columns={columns}
            data={events}
            pageSize={AUDIT_PAGE_SIZE}
            loading={eventsQuery.isFetching && !eventsQuery.isPending}
            emptyMessage={MSG_NO_EVENTS_MATCH}
          />

          <nav
            aria-label="Audit trail pagination"
            className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4 text-xs text-ink2"
          >
            <span>{MSG_EVENTS_COUNT(formatInt(total))}</span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={page <= 1 || eventsQuery.isFetching}
                onClick={() => goToPage(page - 1)}
              >
                {MSG_PREVIOUS}
              </Button>
              <span className="px-1 tabular-nums">{MSG_PAGE_OF(page, totalPages)}</span>
              <Button
                variant="secondary"
                size="sm"
                disabled={page >= totalPages || eventsQuery.isFetching}
                onClick={() => goToPage(page + 1)}
              >
                {MSG_NEXT}
              </Button>
            </div>
          </nav>

          <p className="mt-4 text-xs text-ink2">
            Entries are hash-chained and cannot be edited or deleted.
          </p>
        </motion.div>
      ) : null}
    </div>
  );
}

export default AuditPage;
