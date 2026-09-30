import { useEffect, useMemo, useRef, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import {
  IconDotsVertical,
  IconSearch,
  IconUserPlus,
  IconUsers,
} from "@tabler/icons-react";
import { Can } from "../../../auth/Can";
import { usePermission } from "../../../auth/permissions";
import { useSessionStore } from "../../../auth/session.store";
import type { Role, User } from "../../../api/schema";
import { Badge } from "../../../shared/ui/Badge";
import { Button } from "../../../shared/ui/Button";
import { DataTable } from "../../../shared/ui/DataTable";
import { EmptyState } from "../../../shared/ui/EmptyState";
import { Input } from "../../../shared/ui/Input";
import { Modal } from "../../../shared/ui/Modal";
import { Select } from "../../../shared/ui/Select";
import { Skeleton } from "../../../shared/ui/Skeleton";
import { useToast } from "../../../shared/ui/Toast";
import { useDebounce } from "../../../shared/hooks/useDebounce";
import { cx, formatDateTime, formatInt } from "../../../shared/lib/format";
import {
  MSG_ACTIONS,
  MSG_CANCEL,
  MSG_CHANGE_ROLE,
  MSG_CONFIRM,
  MSG_DEACTIVATE,
  MSG_DEACTIVATE_FAILED,
  MSG_DEACTIVATE_USER_CONFIRM,
  MSG_INVITE_USER,
  MSG_LAST_SIGN_IN,
  MSG_LOADING,
  MSG_NEXT,
  MSG_NO_USERS,
  MSG_PAGE_OF,
  MSG_PREVIOUS,
  MSG_ROLE,
  MSG_ROLE_CHANGE_FAILED,
  MSG_ROLE_UPDATED,
  MSG_SAVE,
  MSG_SEARCH_BY_EMAIL,
  MSG_SEARCH_USERS_PLACEHOLDER,
  MSG_STATUS,
  MSG_USER,
  MSG_USER_DEACTIVATED,
  MSG_USERS_COUNT,
  MSG_USERS_LOAD_FAILED,
  MSG_USERS_SUBTITLE,
  MSG_USERS_TITLE,
  MSG_YOU,
} from "../../../shared/constants/messages";
import {
  USERS_PAGE_SIZE,
  changeRoleErrorMessage,
  deactivateErrorMessage,
  useChangeRole,
  useDeactivate,
  useUsers,
} from "../api";
import { InviteUserModal } from "../components/InviteUserModal";
import {
  ROLE_LABELS,
  ROLE_OPTIONS,
  ROLE_VARIANTS,
  USER_STATUS_LABEL,
  USER_STATUS_VARIANT,
  isCurrentUser,
  userDisplayName,
} from "../schemas";

interface UserActionsProps {
  user: User;
  onChangeRole: (user: User) => void;
  onDeactivate: (user: User) => void;
}

/**
 * Per-row actions menu (PRD S8: Change role, Deactivate).
 *
 * Hidden entirely on the signed-in user's own row — an Administrator cannot
 * deactivate themselves, and a role change on their own row would be a lockout
 * (hidden, not disabled — PRD Section 2 RBAC rule).
 */
function UserActions({ user, onChangeRole, onDeactivate }: UserActionsProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsOpen(false);
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  return (
    <div ref={containerRef} className="relative inline-block text-left">
      <button
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-label={`${MSG_ACTIONS} · ${user.email}`}
        className={cx(
          "rounded-md p-1.5 text-[#6c757d] transition-colors dark:text-[#a0aec0]",
          "hover:bg-[#f2f3f7] dark:hover:bg-[#2d3239] hover:text-[#1f2937] dark:hover:text-[#f3f4f6]",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#fd6321]"
        )}
      >
        <IconDotsVertical className="h-4 w-4" aria-hidden="true" />
      </button>

      {isOpen && (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-md border border-[#e9ecef] bg-white py-1 shadow-lg dark:border-[#343a40] dark:bg-[#24282e]"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setIsOpen(false);
              onChangeRole(user);
            }}
            className="flex w-full items-center px-3 py-2 text-left text-sm text-[#1f2937] hover:bg-[#f8f9fa] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#fd6321] dark:text-[#f3f4f6] dark:hover:bg-[#2d3239]"
          >
            {MSG_CHANGE_ROLE}
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setIsOpen(false);
              onDeactivate(user);
            }}
            disabled={user.status === "deactivated"}
            className="flex w-full items-center px-3 py-2 text-left text-sm text-[#dc3545] hover:bg-[#f8d7da]/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#fd6321] disabled:cursor-not-allowed disabled:opacity-50 dark:text-[#f17c85] dark:hover:bg-[#3d1a1c]/60"
          >
            {MSG_DEACTIVATE}
          </button>
        </div>
      )}
    </div>
  );
}

interface ChangeRoleModalProps {
  user: User | null;
  onClose: () => void;
  onSubmit: (user: User, role: Role) => Promise<void>;
  pending: boolean;
  error: string | null;
}

/** Role picker for the Change role action. One role per user (OQ-21). */
function ChangeRoleModal({
  user,
  onClose,
  onSubmit,
  pending,
  error,
}: ChangeRoleModalProps) {
  const [role, setRole] = useState<Role>(user?.role ?? "viewer");

  useEffect(() => {
    if (!user) return;
    setRole(user.role);
  }, [user]);

  if (!user) return null;

  return (
    <Modal
      isOpen
      onClose={pending ? () => undefined : onClose}
      title={MSG_CHANGE_ROLE}
      description={user.email}
      maxWidth="sm"
      closeOnOverlayClick={!pending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            {MSG_CANCEL}
          </Button>
          <Button
            onClick={() => void onSubmit(user, role)}
            loading={pending}
          >
            {MSG_SAVE}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Select
          label={
            <>
              {MSG_ROLE}{" "}
              <span className="font-bold text-red-500" aria-hidden="true">
                *
              </span>
            </>
          }
          required
          value={role}
          disabled={pending}
          onChange={(event) => setRole(event.target.value as Role)}
          options={ROLE_OPTIONS}
        />

        {error && (
          <p
            role="alert"
            className="rounded-md border border-[#f5c6cb] bg-[#f8d7da] px-3 py-2 text-sm text-[#721c24] dark:border-[#662025] dark:bg-[#3d1a1c] dark:text-[#f5a3a9]"
          >
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}

interface DeactivateModalProps {
  user: User | null;
  onClose: () => void;
  onConfirm: (user: User) => Promise<void>;
  pending: boolean;
  error: string | null;
}

/** Deactivate confirmation (PRD S8, wireframe 1k). */
function DeactivateModal({
  user,
  onClose,
  onConfirm,
  pending,
  error,
}: DeactivateModalProps) {
  if (!user) return null;

  return (
    <Modal
      isOpen
      onClose={pending ? () => undefined : onClose}
      title={MSG_DEACTIVATE}
      description={user.email}
      maxWidth="sm"
      closeOnOverlayClick={!pending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            {MSG_CANCEL}
          </Button>
          <Button
            variant="danger"
            onClick={() => void onConfirm(user)}
            loading={pending}
          >
            {MSG_CONFIRM}
          </Button>
        </>
      }
    >
      <p className="text-sm text-[#1f2937] dark:text-[#f3f4f6]">
        {MSG_DEACTIVATE_USER_CONFIRM}
      </p>

      {error && (
        <p
          role="alert"
          className="mt-3 rounded-md border border-[#f5c6cb] bg-[#f8d7da] px-3 py-2 text-sm text-[#721c24] dark:border-[#662025] dark:bg-[#3d1a1c] dark:text-[#f5a3a9]"
        >
          {error}
        </p>
      )}
    </Modal>
  );
}

/**
 * S8 Users & roles (PRD Section 7, wireframe 1k).
 * Server-paged grid with a per-row actions menu. The administrator's own row
 * carries no actions, so nobody can deactivate or demote themselves.
 */
export function UsersPage() {
  const toast = useToast();
  const canEdit = usePermission("users.edit");
  const currentUserId = useSessionStore((state) => state.user?.id);

  const [searchInput, setSearchInput] = useState("");
  const search = useDebounce(searchInput, 300);
  const [page, setPage] = useState(1);
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [roleTarget, setRoleTarget] = useState<User | null>(null);
  const [deactivateTarget, setDeactivateTarget] = useState<User | null>(null);
  const [modalError, setModalError] = useState<string | null>(null);

  const { data, isPending, isFetching, isError, error } = useUsers({
    page,
    pageSize: USERS_PAGE_SIZE,
    search,
  });

  const changeRoleMutation = useChangeRole();
  const deactivateMutation = useDeactivate();

  const users = useMemo(() => data?.items ?? [], [data?.items]);
  const total = data?.total ?? 0;
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / USERS_PAGE_SIZE)),
    [total]
  );

  // A new search always restarts at the first page.
  useEffect(() => {
    setPage(1);
  }, [search]);

  // Keep the pager inside the result set when a page becomes unreachable.
  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  useEffect(() => {
    setModalError(null);
  }, [roleTarget, deactivateTarget]);

  const columns = useMemo<ColumnDef<User, any>[]>(() => {
    return [
      {
        id: "user",
        header: MSG_USER,
        accessorFn: (row) => userDisplayName(row),
        cell: ({ row }) => (
          <div className="flex flex-col">
            <span className="flex items-center gap-2 font-medium text-[#1f2937] dark:text-[#f3f4f6]">
              {userDisplayName(row.original)}
              {isCurrentUser(row.original, currentUserId) && (
                <span className="text-xs font-normal text-[#6c757d] dark:text-[#a0aec0]">
                  ({MSG_YOU})
                </span>
              )}
            </span>
            <span className="text-xs text-[#6c757d] dark:text-[#a0aec0]">
              {row.original.email}
            </span>
          </div>
        ),
      },
      {
        id: "role",
        header: MSG_ROLE,
        accessorFn: (row) => ROLE_LABELS[row.role] ?? row.role,
        cell: ({ row }) => (
          <Badge variant={ROLE_VARIANTS[row.original.role]}>
            {ROLE_LABELS[row.original.role] ?? row.original.role}
          </Badge>
        ),
      },
      {
        id: "status",
        header: MSG_STATUS,
        accessorFn: (row) => row.status,
        cell: ({ row }) => (
          <Badge variant={USER_STATUS_VARIANT[row.original.status]}>
            {USER_STATUS_LABEL[row.original.status] ?? row.original.status}
          </Badge>
        ),
      },
      {
        id: "lastLoginAt",
        header: MSG_LAST_SIGN_IN,
        accessorFn: (row) => row.lastLoginAt ?? "",
        cell: ({ row }) => (
          <span className="tabular-nums">
            {formatDateTime(row.original.lastLoginAt)}
          </span>
        ),
      },
      {
        id: "actions",
        header: MSG_ACTIONS,
        enableSorting: false,
        cell: ({ row }) => {
          const isSelf = isCurrentUser(row.original, currentUserId);
          if (!canEdit || isSelf) return null;
          return (
            <UserActions
              user={row.original}
              onChangeRole={(user) => setRoleTarget(user)}
              onDeactivate={(user) => setDeactivateTarget(user)}
            />
          );
        },
      },
    ];
  }, [canEdit, currentUserId]);

  const handleChangeRole = async (user: User, role: Role) => {
    if (role === user.role) {
      setRoleTarget(null);
      return;
    }
    setModalError(null);
    try {
      await changeRoleMutation.mutateAsync({ id: user.id, role });
      toast.success(MSG_ROLE_UPDATED);
      setRoleTarget(null);
    } catch (error) {
      setModalError(changeRoleErrorMessage(error) || MSG_ROLE_CHANGE_FAILED);
    }
  };

  const handleDeactivate = async (user: User) => {
    setModalError(null);
    try {
      await deactivateMutation.mutateAsync({ id: user.id });
      toast.success(MSG_USER_DEACTIVATED);
      setDeactivateTarget(null);
    } catch (error) {
      setModalError(deactivateErrorMessage(error) || MSG_DEACTIVATE_FAILED);
    }
  };

  const showSkeleton = isPending && !data;
  const showEmpty = !isPending && !isError && users.length === 0;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[#1f2937] dark:text-[#f3f4f6]">
            {MSG_USERS_TITLE}
          </h1>
          <p className="mt-0.5 text-sm text-[#6c757d] dark:text-[#a0aec0]">
            {MSG_USERS_SUBTITLE}
          </p>
        </div>
        <Can perm="users.invite">
          <Button
            leftIcon={<IconUserPlus className="h-4 w-4" aria-hidden="true" />}
            onClick={() => setIsInviteOpen(true)}
          >
            {MSG_INVITE_USER}
          </Button>
        </Can>
      </header>

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-full max-w-xs">
          <Input
            type="search"
            label={MSG_SEARCH_BY_EMAIL}
            value={searchInput}
            placeholder={MSG_SEARCH_USERS_PLACEHOLDER}
            autoComplete="off"
            onChange={(event) => setSearchInput(event.target.value)}
            leftIcon={<IconSearch className="h-4 w-4" aria-hidden="true" />}
          />
        </div>
      </div>

      {isError && (
        <div
          role="alert"
          className="rounded-md border border-[#f5c6cb] bg-[#f8d7da] px-4 py-3 text-sm text-[#721c24] dark:border-[#662025] dark:bg-[#3d1a1c] dark:text-[#f5a3a9]"
        >
          {error?.detail || error?.title || MSG_USERS_LOAD_FAILED}
        </div>
      )}

      {showSkeleton ? (
        <div className="space-y-3" role="status" aria-label={MSG_LOADING(MSG_USERS_TITLE)}>
          <Skeleton className="h-12 w-full rounded-lg" />
          <Skeleton className="h-64 w-full rounded-lg" />
        </div>
      ) : showEmpty ? (
        <EmptyState
          icon={<IconUsers className="h-6 w-6 stroke-[1.5]" aria-hidden="true" />}
          message={MSG_NO_USERS}
        />
      ) : (
        <>
          <DataTable
            columns={columns}
            data={users}
            pageSize={USERS_PAGE_SIZE}
            loading={isFetching && !isPending}
            emptyMessage={MSG_NO_USERS}
          />

          <nav
            aria-label="Users pagination"
            className="flex flex-wrap items-center justify-between gap-3 text-xs text-[#6c757d] dark:text-[#a0aec0]"
          >
            <span>{MSG_USERS_COUNT(formatInt(total))}</span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={page <= 1 || isFetching}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                {MSG_PREVIOUS}
              </Button>
              <span className="px-1 tabular-nums">{MSG_PAGE_OF(page, totalPages)}</span>
              <Button
                variant="secondary"
                size="sm"
                disabled={page >= totalPages || isFetching}
                onClick={() => setPage((current) => current + 1)}
              >
                {MSG_NEXT}
              </Button>
            </div>
          </nav>
        </>
      )}

      <InviteUserModal
        isOpen={isInviteOpen}
        onClose={() => setIsInviteOpen(false)}
      />

      <ChangeRoleModal
        user={roleTarget}
        onClose={() => setRoleTarget(null)}
        onSubmit={handleChangeRole}
        pending={changeRoleMutation.isPending}
        error={modalError}
      />

      <DeactivateModal
        user={deactivateTarget}
        onClose={() => setDeactivateTarget(null)}
        onConfirm={handleDeactivate}
        pending={deactivateMutation.isPending}
        error={modalError}
      />
    </div>
  );
}

export default UsersPage;
