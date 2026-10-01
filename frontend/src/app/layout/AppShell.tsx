import { useState, useEffect, type ReactNode } from "react";
import { Outlet, NavLink, useNavigate, Navigate } from "react-router";
import {
  IconDatabase,
  IconSettings,
  IconUsers,
  IconFileText,
  IconFlask,
  IconLogout,
  IconWifiOff,
} from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useSessionStore, type Role } from "../../auth/session.store";
import { usePermission, type Permission } from "../../auth/permissions";
import { api } from "../../api/client";
import { MESSAGES } from "../../shared/constants/messages";
import { Badge, type BadgeVariant } from "../../shared/ui/Badge";
import { Button } from "../../shared/ui/Button";
import { cx } from "../../shared/lib/format";

interface NavItem {
  label: string;
  path: string;
  icon: typeof IconDatabase;
  perm: Permission;
}

const NAV_ITEMS: NavItem[] = [
  {
    label: "Datasets",
    path: "/datasets",
    icon: IconDatabase,
    perm: "dataset.view",
  },
  {
    label: "Model settings",
    path: "/settings/model",
    icon: IconSettings,
    perm: "model.view",
  },
  {
    label: "Users",
    path: "/settings/users",
    icon: IconUsers,
    perm: "users.view",
  },
  {
    label: "Audit trail",
    path: "/audit",
    icon: IconFileText,
    perm: "audit.view",
  },
  {
    label: "Evaluation",
    path: "/evaluation",
    icon: IconFlask,
    perm: "evaluation.run",
  },
];

const ROLE_LABELS: Record<Role, { label: string; variant: BadgeVariant }> = {
  data_engineer: { label: "Data Engineer", variant: "info" },
  administrator: { label: "Administrator", variant: "warning" },
  auditor: { label: "Auditor", variant: "secondary" },
  viewer: { label: "Viewer", variant: "secondary" },
};

/**
 * RequireAuth guard: if no accessToken is held in memory, redirects to /login.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const accessToken = useSessionStore((state) => state.accessToken);

  if (!accessToken) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

export function AppShell() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const user = useSessionStore((state) => state.user);
  const clearSession = useSessionStore((state) => state.clearSession);

  const [isOnline, setIsOnline] = useState<boolean>(
    typeof navigator !== "undefined" ? navigator.onLine : true
  );
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const handleSignOut = async () => {
    setIsLoggingOut(true);
    try {
      await api.post("auth/logout");
    } catch {
      // Best-effort logout
    } finally {
      clearSession();
      queryClient.clear();
      setIsLoggingOut(false);
      navigate("/login");
    }
  };

  const roleInfo = user?.role ? ROLE_LABELS[user.role] : undefined;

  return (
    <div className="flex h-screen w-full overflow-hidden bg-canvas dark:bg-[#1a1d21] text-ink dark:text-[#f3f4f6]">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 flex flex-col bg-surface dark:bg-[#1f2327] border-r border-line dark:border-[#343a40] z-20">
        {/* Brand header */}
        <div className="h-16 flex items-center px-6 border-b border-line dark:border-[#343a40]">
          <div>
            <h1 className="text-base font-bold text-ink dark:text-[#f3f4f6] tracking-wide leading-tight">
              TITAN
            </h1>
            <p className="text-xs text-ink2 dark:text-[#a0aec0]">
              Data Cleaning
            </p>
          </div>
        </div>

        {/* Navigation list */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1" aria-label="Main sidebar">
          {NAV_ITEMS.map((item) => (
            <SidebarItem key={item.path} item={item} />
          ))}
        </nav>
      </aside>

      {/* Main Column */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Offline Banner */}
        {!isOnline && (
          <div
            role="status"
            className="w-full bg-amber-500 text-white text-xs font-semibold py-2 px-4 flex items-center justify-center gap-2 z-30 shadow-sm"
          >
            <IconWifiOff className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
            <span>{MESSAGES.OFFLINE}</span>
          </div>
        )}

        {/* Top Header */}
        <header className="h-16 flex-shrink-0 bg-surface dark:bg-[#24282e] border-b border-line dark:border-[#343a40] flex items-center justify-between px-6 z-10">
          <div className="flex items-center gap-4">
            {/* Title / context can be augmented by routes */}
          </div>

          {/* User profile & actions */}
          <div className="flex items-center gap-4">
            {user && (
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <p className="text-xs font-bold text-ink dark:text-[#f3f4f6]">
                    {user.name || user.email}
                  </p>
                  {roleInfo && (
                    <div className="mt-0.5">
                      <Badge variant={roleInfo.variant}>{roleInfo.label}</Badge>
                    </div>
                  )}
                </div>
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 dark:bg-[#3d2420] text-primary font-bold text-xs uppercase border border-primary/20">
                  {(user.name || user.email).charAt(0)}
                </div>
              </div>
            )}

            <div className="h-6 w-px bg-line dark:bg-[#343a40]" />

            <Button
              variant="ghost"
              size="sm"
              loading={isLoggingOut}
              onClick={handleSignOut}
              leftIcon={<IconLogout className="h-4 w-4" aria-hidden="true" />}
              className="text-ink2 hover:text-danger dark:text-[#a0aec0] dark:hover:text-[#dc3545]"
            >
              {MESSAGES.SIGN_OUT}
            </Button>
          </div>
        </header>

        {/* Page Content Viewport */}
        <main className="flex-1 overflow-y-auto p-6 bg-canvas dark:bg-[#1a1d21]">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

/**
 * Filtered Sidebar Navigation Item.
 * Hidden if the authenticated role lacks the required permission.
 */
function SidebarItem({ item }: { item: NavItem }) {
  const isAllowed = usePermission(item.perm);
  const Icon = item.icon;

  if (!isAllowed) return null;

  return (
    <NavLink
      to={item.path}
      className={({ isActive }) =>
        cx(
          "flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors select-none",
          isActive
            ? "bg-primary text-white shadow-sm"
            : "text-ink2 dark:text-[#cbd5e1] hover:bg-canvas dark:hover:bg-[#2d3239] hover:text-ink dark:hover:text-[#f3f4f6]"
        )
      }
    >
      <Icon className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
      <span>{item.label}</span>
    </NavLink>
  );
}
