import { z } from "zod";
import type { BadgeVariant } from "../../shared/ui/Badge";
import type { User, UserStatus } from "../../api/schema";
import { MSG_ENTER_VALID_EMAIL } from "../../shared/constants/messages";

/**
 * S8 Users & roles schemas and the role/status vocabularies the grid renders.
 * One role per user (OQ-21), so the role field is a single-choice enum.
 */

export const EMAIL_MAX = 254;

export const roleSchema = z.enum([
  "data_engineer",
  "administrator",
  "auditor",
  "viewer",
]);

export type Role = z.infer<typeof roleSchema>;

/** PRD Section 2 / wireframe 1c role names, as shown to the user. */
export const ROLE_LABELS: Record<Role, string> = {
  data_engineer: "Data Engineer",
  administrator: "Administrator",
  auditor: "Auditor",
  viewer: "Viewer",
};

export const ROLE_OPTIONS: Array<{ value: Role; label: string }> = [
  { value: "data_engineer", label: ROLE_LABELS.data_engineer },
  { value: "administrator", label: ROLE_LABELS.administrator },
  { value: "auditor", label: ROLE_LABELS.auditor },
  { value: "viewer", label: ROLE_LABELS.viewer },
];

/** Role badge colours; the label is always shown (WCAG 2.1 AA). */
export const ROLE_VARIANTS: Record<Role, BadgeVariant> = {
  data_engineer: "info",
  administrator: "warning",
  auditor: "secondary",
  viewer: "secondary",
};

/** PRD S8 grid status vocabulary. */
export const USER_STATUS_LABEL: Record<UserStatus, string> = {
  invited: "Invited",
  active: "Active",
  deactivated: "Deactivated",
};

export const USER_STATUS_VARIANT: Record<UserStatus, BadgeVariant> = {
  invited: "warning",
  active: "success",
  deactivated: "secondary",
};

/**
 * Invite form (PRD S8, wireframe 1k): a work email and one of the four roles.
 * A duplicate address is reported by the backend as 409, which the page maps
 * onto the same copy.
 */
export const inviteSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, MSG_ENTER_VALID_EMAIL)
    .max(EMAIL_MAX, MSG_ENTER_VALID_EMAIL)
    .email(MSG_ENTER_VALID_EMAIL),
  role: roleSchema,
});

export type InviteFormValues = z.infer<typeof inviteSchema>;

/** Role picker for the Change role action; the value must be one of the four. */
export const changeRoleSchema = z.object({
  role: roleSchema,
});

export type ChangeRoleFormValues = z.infer<typeof changeRoleSchema>;

/** "First Last" when the account has a name, otherwise the email address. */
export function userDisplayName(user: Pick<User, "firstName" | "lastName" | "email">): string {
  const full = [user.firstName, user.lastName]
    .filter((part): part is string => Boolean(part && part.trim()))
    .join(" ")
    .trim();
  return full || user.email;
}

/** True when the row belongs to the signed-in user (their own actions are hidden). */
export function isCurrentUser(
  row: Pick<User, "id">,
  currentUserId: string | undefined | null
): boolean {
  return Boolean(currentUserId) && row.id === currentUserId;
}
