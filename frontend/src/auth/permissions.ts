import { type Role, useSessionStore } from "./session.store";
export type { Role };

export type Permission =
  | "dataset.upload"
  | "dataset.view"
  | "profile.view"
  | "plan.generate"
  | "plan.decide"
  | "plan.approve"
  | "plan.rollback"
  | "export"
  | "evaluation.run"
  | "model.view"
  | "model.edit"
  | "users.view"
  | "users.invite"
  | "users.edit"
  | "audit.view"
  | "audit.export";

/**
 * Role-Based Access Control permission matrix (PRD Section 2 / Wireframe 1c)
 */
export const PERMISSIONS: Record<Role, readonly Permission[]> = {
  data_engineer: [
    "dataset.upload",
    "dataset.view",
    "profile.view",
    "plan.generate",
    "plan.decide",
    "plan.approve",
    "plan.rollback",
    "export",
    "evaluation.run",
  ],
  administrator: [
    "model.view",
    "model.edit",
    "users.view",
    "users.invite",
    "users.edit",
    "audit.view",
    "evaluation.run",
  ],
  auditor: [
    "dataset.view",
    "profile.view",
    "audit.view",
    "audit.export",
  ],
  viewer: [
    "dataset.view",
    "profile.view",
    "export",
  ],
};

/**
 * Checks if a specific role possesses the requested permission.
 */
export function hasPermission(role: Role | undefined | null, perm: Permission): boolean {
  if (!role) return false;
  const rolePermissions = PERMISSIONS[role];
  return rolePermissions ? rolePermissions.includes(perm) : false;
}

/**
 * Hook to check if the currently authenticated user has the requested permission.
 */
export function usePermission(perm: Permission): boolean {
  const user = useSessionStore((state) => state.user);
  return hasPermission(user?.role, perm);
}

/**
 * Default landing route per role (PRD Section 2).
 */
export function getRoleLandingRoute(role: Role): string {
  switch (role) {
    case "data_engineer":
      return "/datasets";
    case "administrator":
      return "/settings/model";
    case "auditor":
      return "/audit";
    case "viewer":
      return "/datasets";
  }
}
