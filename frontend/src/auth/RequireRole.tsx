import type { ReactNode } from "react";
import { useSessionStore } from "./session.store";
import { type Permission, type Role, hasPermission } from "./permissions";
import { Forbidden } from "../pages/Forbidden";

export interface RequireRoleProps {
  children: ReactNode;
  role?: Role | Role[];
  perm?: Permission;
}

/**
 * Route / Component guard enforcing role or permission requirements.
 * Renders Forbidden (403) page if unauthenticated or not permitted.
 */
export function RequireRole({ children, role, perm }: RequireRoleProps) {
  const user = useSessionStore((state) => state.user);

  if (!user) {
    return <Forbidden />;
  }

  if (role) {
    const allowedRoles = Array.isArray(role) ? role : [role];
    if (!allowedRoles.includes(user.role)) {
      return <Forbidden />;
    }
  }

  if (perm && !hasPermission(user.role, perm)) {
    return <Forbidden />;
  }

  return <>{children}</>;
}
