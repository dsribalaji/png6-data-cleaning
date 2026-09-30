import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  IconCheck,
  IconChevronDown,
  IconFilterOff,
  IconX,
} from "@tabler/icons-react";
import type { User } from "../../../api/schema";
import { ROLE_LABELS, userDisplayName } from "../../users/schemas";
import { Badge } from "../../../shared/ui/Badge";
import { Button } from "../../../shared/ui/Button";
import { Input } from "../../../shared/ui/Input";
import { Select } from "../../../shared/ui/Select";
import { cx } from "../../../shared/lib/format";
import {
  MSG_ALL_EVENT_TYPES,
  MSG_ALL_USERS,
  MSG_CLEAR_FILTERS,
  MSG_EVENT_TYPE,
  MSG_EXPORTING_CSV,
  MSG_FROM,
  MSG_REMOVE_EVENT_TYPE_FILTER,
  MSG_TO,
  MSG_USER,
  MSG_USER_FILTER_UNAVAILABLE,
  eventTypesSelected,
} from "../../../shared/constants/messages";
import {
  AUDIT_EVENT_TYPES,
  auditRangeError,
  isKnownAuditEventType,
  type AuditEventType,
  type AuditFiltersState,
} from "../api";

export interface AuditFiltersProps {
  filters: AuditFiltersState;
  onChange: (next: AuditFiltersState) => void;
  onClear: () => void;
  /** Options for the User select; empty when the role cannot list users. */
  users: User[];
  usersLoading?: boolean;
  /**
   * `GET /users` needs `users.view`, which an Auditor does not hold. When the
   * role cannot list accounts the select stays on "All users" and says so,
   * instead of firing a request that would 403.
   */
  canFilterByUser: boolean;
  disabled?: boolean;
  isExporting?: boolean;
  exportAction?: ReactNode;
}

/**
 * S9 filter bar (PRD Section 7, wireframe 1l).
 *
 * Controlled: the owning page holds the state and keeps it mirrored in the URL
 * query, so a filtered audit trail can be shared as a link.
 */
export function AuditFilters({
  filters,
  onChange,
  onClear,
  users,
  usersLoading = false,
  canFilterByUser,
  disabled = false,
  isExporting = false,
  exportAction,
}: AuditFiltersProps) {
  const [isEventPanelOpen, setIsEventPanelOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const rangeError = auditRangeError(filters);
  const selectedTypes = filters.eventTypes;

  useEffect(() => {
    if (!isEventPanelOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (!panelRef.current?.contains(event.target as Node)) {
        setIsEventPanelOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsEventPanelOpen(false);
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isEventPanelOpen]);

  const toggleEventType = (eventType: string) => {
    const next = selectedTypes.includes(eventType)
      ? selectedTypes.filter((value) => value !== eventType)
      : [...selectedTypes, eventType];
    onChange({ ...filters, eventTypes: next });
  };

  const hasFilters = Boolean(
    filters.fromDate || filters.toDate || filters.userId || selectedTypes.length > 0
  );

  return (
    <div className="rounded-lg border border-[#e9ecef] bg-white p-4 dark:border-[#343a40] dark:bg-[#24282e]">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-full max-w-[11rem]">
          <Input
            type="date"
            label={MSG_FROM}
            value={filters.fromDate ?? ""}
            disabled={disabled}
            onChange={(event) =>
              onChange({
                ...filters,
                fromDate: event.target.value || undefined,
              })
            }
          />
        </div>

        <div className="w-full max-w-[11rem]">
          <Input
            type="date"
            label={MSG_TO}
            value={filters.toDate ?? ""}
            disabled={disabled}
            error={rangeError ?? undefined}
            min={filters.fromDate || undefined}
            onChange={(event) =>
              onChange({ ...filters, toDate: event.target.value || undefined })
            }
          />
        </div>

        {/* Event type multi-select. A checkbox list keeps it keyboard reachable,
            which a native multiple select is not. */}
        <div className="relative w-full max-w-[14rem]" ref={panelRef}>
          <span className="mb-1.5 block text-xs font-semibold text-[#1f2937] dark:text-[#f3f4f6]">
            {MSG_EVENT_TYPE}
          </span>
          <button
            type="button"
            disabled={disabled}
            onClick={() => setIsEventPanelOpen((current) => !current)}
            aria-haspopup="true"
            aria-expanded={isEventPanelOpen}
            className={cx(
              "flex w-full items-center justify-between gap-2 rounded-md border px-3.5 py-2 text-sm shadow-sm transition-colors",
              "bg-white text-[#1f2937] dark:bg-[#1a1d21] dark:text-[#f3f4f6]",
              "border-[#d1d5db] dark:border-[#374151] focus:outline-none focus:ring-1 focus:ring-[#fd6321]",
              "disabled:cursor-not-allowed disabled:opacity-60"
            )}
          >
            <span className="truncate">
              {selectedTypes.length === 0
                ? MSG_ALL_EVENT_TYPES
                : eventTypesSelected(selectedTypes.length)}
            </span>
            <IconChevronDown
              className={cx(
                "h-4 w-4 flex-shrink-0 text-[#6c757d] transition-transform dark:text-[#a0aec0]",
                isEventPanelOpen && "rotate-180"
              )}
              aria-hidden="true"
            />
          </button>

          {isEventPanelOpen && (
            <div className="absolute left-0 z-20 mt-1 w-64 rounded-md border border-[#e9ecef] bg-white py-2 shadow-lg dark:border-[#343a40] dark:bg-[#24282e]">
              <fieldset className="max-h-64 overflow-y-auto px-3">
                <legend className="sr-only">{MSG_EVENT_TYPE}</legend>
                {AUDIT_EVENT_TYPES.map((eventType) => {
                  const checked = selectedTypes.includes(eventType);
                  const id = `audit-event-type-${eventType.replace(/\./g, "-")}`;
                  return (
                    <label
                      key={eventType}
                      htmlFor={id}
                      className="flex cursor-pointer items-center gap-2.5 rounded px-1 py-1.5 text-sm text-[#1f2937] hover:bg-[#f8f9fa] dark:text-[#f3f4f6] dark:hover:bg-[#2d3239]"
                    >
                      <input
                        id={id}
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleEventType(eventType)}
                        className="h-4 w-4 rounded border-[#d1d5db] text-[#fd6321] focus:ring-2 focus:ring-[#fd6321] dark:border-[#374151] dark:bg-[#1a1d21]"
                      />
                      <span className="font-mono text-xs">{eventType}</span>
                    </label>
                  );
                })}
              </fieldset>
            </div>
          )}
        </div>

        <div className="w-full max-w-[15rem]">
          <Select
            label={MSG_USER}
            value={filters.userId ?? ""}
            disabled={disabled || !canFilterByUser || usersLoading}
            onChange={(event) =>
              onChange({ ...filters, userId: event.target.value || undefined })
            }
            hint={canFilterByUser ? undefined : MSG_USER_FILTER_UNAVAILABLE}
            options={[
              { value: "", label: MSG_ALL_USERS },
              ...users.map((user) => ({
                value: user.id,
                label: `${userDisplayName(user)} · ${ROLE_LABELS[user.role]}`,
              })),
            ]}
          />
        </div>

        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={onClear}
            disabled={disabled || !hasFilters}
            leftIcon={<IconFilterOff className="h-3.5 w-3.5" aria-hidden="true" />}
          >
            {MSG_CLEAR_FILTERS}
          </Button>
          {exportAction}
        </div>
      </div>

      {/* Selected event types, removable one by one. */}
      {selectedTypes.length > 0 && (
        <ul className="mt-3 flex flex-wrap items-center gap-2">
          {selectedTypes.map((eventType) => {
            const known: AuditEventType | null = isKnownAuditEventType(eventType)
              ? eventType
              : null;
            return (
              <li key={eventType}>
                <Badge
                  variant="info"
                  className="pr-1"
                  icon={known ? <IconCheck className="h-3 w-3" /> : undefined}
                >
                  <span className="font-mono">{eventType}</span>
                  <button
                    type="button"
                    onClick={() => toggleEventType(eventType)}
                    disabled={disabled}
                    aria-label={MSG_REMOVE_EVENT_TYPE_FILTER(eventType)}
                    className="ml-1 rounded p-0.5 hover:bg-blue-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#fd6321] dark:hover:bg-blue-900/60"
                  >
                    <IconX className="h-3 w-3" aria-hidden="true" />
                  </button>
                </Badge>
              </li>
            );
          })}
        </ul>
      )}

      {isExporting && (
        <p role="status" className="mt-3 text-xs text-[#6c757d] dark:text-[#a0aec0]">
          {MSG_EXPORTING_CSV}
        </p>
      )}
    </div>
  );
}

export default AuditFilters;
