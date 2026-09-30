import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
  type UseMutationResult,
  type UseQueryOptions,
  type UseQueryResult,
} from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import type {
  InviteUserRequest,
  Page,
  Role,
  UpdateUserRoleRequest,
  User,
  UserInvite,
} from "../../api/schema";
import {
  MSG_DEACTIVATE_FAILED,
  MSG_INVITE_FAILED,
  MSG_ROLE_CHANGE_FAILED,
  MSG_USER_EXISTS,
} from "../../shared/constants/messages";

/**
 * S8 Users & roles server state (PRD Section 7, wireframe 1k).
 * The list is server-paged so the page never has to hold every account, and
 * the same hook backs the user pickers other screens need.
 */

export const USERS_PAGE_SIZE = 50;

/** Upper bound for the user pickers (the S9 audit filter). */
export const USER_OPTION_LIMIT = 200;

export const userKeys = {
  all: ["users"] as const,
  list: (params: UsersListParams) => ["users", params] as const,
};

export interface UsersListParams {
  page?: number;
  pageSize?: number;
  search?: string;
}

function toSearchParams(params: UsersListParams): URLSearchParams {
  const search = new URLSearchParams();
  if (params.page) search.set("page", String(params.page));
  if (params.pageSize) search.set("pageSize", String(params.pageSize));
  if (params.search) search.set("search", params.search);
  return search;
}

/** GET /users — paginated list of accounts. */
export function useUsers(
  params: UsersListParams = {},
  options?: Omit<UseQueryOptions<Page<User>, ApiError>, "queryKey" | "queryFn">
): UseQueryResult<Page<User>, ApiError> {
  return useQuery<Page<User>, ApiError>({
    queryKey: userKeys.list(params),
    queryFn: () => {
      const search = toSearchParams(params).toString();
      return api.get(`users${search ? `?${search}` : ""}`).json<Page<User>>();
    },
    placeholderData: keepPreviousData,
    ...options,
  });
}

/**
 * Replaces a user inside every cached list so the row updates the moment the
 * mutation resolves, without waiting for the invalidation round trip.
 */
export function patchUserInCaches(queryClient: QueryClient, updated: User): void {
  const lists = queryClient.getQueryCache().findAll({ queryKey: userKeys.all });

  for (const query of lists) {
    const key = query.queryKey;
    // `findAll` also matches the `["users"]` root entry; only patch pages.
    if (key.length !== 2) continue;

    queryClient.setQueryData<Page<User>>(key, (previous) => {
      if (!previous || !Array.isArray(previous.items)) return previous;
      if (!previous.items.some((item) => item.id === updated.id)) return previous;
      return {
        ...previous,
        items: previous.items.map((item) =>
          item.id === updated.id ? { ...item, ...updated } : item
        ),
      };
    });
  }
}

export type UseInviteUserResult = UseMutationResult<
  UserInvite,
  ApiError,
  InviteUserRequest
>;

/** POST /users/invites — sends an invitation (409 when the user exists). */
export function useInviteUser(): UseInviteUserResult {
  const queryClient = useQueryClient();

  return useMutation<UserInvite, ApiError, InviteUserRequest>({
    mutationFn: (body) => api.post("users/invites", { json: body }).json<UserInvite>(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: userKeys.all });
    },
  });
}

export interface ChangeRoleVariables {
  id: string;
  role: Role;
}

export type UseChangeRoleResult = UseMutationResult<
  User,
  ApiError,
  ChangeRoleVariables
>;

/** PATCH /users/{id}/role — one role per user (OQ-21). */
export function useChangeRole(): UseChangeRoleResult {
  const queryClient = useQueryClient();

  return useMutation<User, ApiError, ChangeRoleVariables>({
    mutationFn: ({ id, role }) => {
      const body: UpdateUserRoleRequest = { role };
      return api.patch(`users/${id}/role`, { json: body }).json<User>();
    },
    onSuccess: (updated) => {
      patchUserInCaches(queryClient, updated);
      void queryClient.invalidateQueries({ queryKey: userKeys.all });
    },
  });
}

export interface DeactivateVariables {
  id: string;
}

export type UseDeactivateResult = UseMutationResult<
  User,
  ApiError,
  DeactivateVariables
>;

/** POST /users/{id}/deactivate — the user is signed out immediately. */
export function useDeactivate(): UseDeactivateResult {
  const queryClient = useQueryClient();

  return useMutation<User, ApiError, DeactivateVariables>({
    mutationFn: ({ id }) =>
      api.post(`users/${id}/deactivate`).json<User>(),
    onSuccess: (updated) => {
      patchUserInCaches(queryClient, updated);
      void queryClient.invalidateQueries({ queryKey: userKeys.all });
    },
  });
}

/**
 * Maps a problem+json failure onto the messages.ts copy and the form field it
 * belongs to (PRD Section 8: ApiError is built from the `code`).
 */
export function mapUsersError(
  error: unknown,
  field: "email" | "form" = "form"
): { field: "email" | "form"; message: string } {
  if (error instanceof ApiError) {
    if (error.status === 409 || error.code === "USER_EXISTS") {
      return { field: "email", message: MSG_USER_EXISTS };
    }
    return { field, message: error.detail || error.title || MSG_INVITE_FAILED };
  }
  return { field, message: MSG_INVITE_FAILED };
}

/** Message shown when a deactivate call fails. */
export function deactivateErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.detail || error.title || MSG_DEACTIVATE_FAILED;
  }
  return MSG_DEACTIVATE_FAILED;
}

/** Message shown when a role change fails. */
export function changeRoleErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.detail || error.title || MSG_ROLE_CHANGE_FAILED;
  }
  return MSG_ROLE_CHANGE_FAILED;
}
