import type { ReactNode } from "react";
import { type Permission, usePermission } from "./permissions";

export interface CanProps {
  perm: Permission;
  children: ReactNode;
  fallback?: ReactNode;
}

/**
 * RBAC wrapper component: renders children only if the current role has the specified permission.
 * By PRD Section 2 rule, unauthorized items are hidden (not disabled).
 */
export function Can({ perm, children, fallback = null }: CanProps) {
  const isAllowed = usePermission(perm);
  return isAllowed ? <>{children}</> : <>{fallback}</>;
}
