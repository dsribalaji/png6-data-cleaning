import { Suspense, lazy, type ReactNode } from "react";
import {
  createBrowserRouter,
  Navigate,
  redirect,
} from "react-router";
import { useSessionStore } from "../auth/session.store";
import {
  type Permission,
  hasPermission,
  getRoleLandingRoute,
} from "../auth/permissions";
import { AppShell, RequireAuth } from "./layout/AppShell";
import { Skeleton } from "../shared/ui/Skeleton";

// -----------------------------------------------------------------------------
// Lazy Loaded Route Pages
// NOTE: Feature page modules (DatasetsPage, etc.) land in the next chunk.
// Lazy imports point to their final file locations so missing modules fail only
// at navigation time, not at initial router setup.
// -----------------------------------------------------------------------------

// Public authentication pages
const LoginPage = lazy(() =>
  import("../auth/pages/LoginPage").then((m) => ({ default: m.LoginPage }))
);
const AcceptInvitePage = lazy(() =>
  import("../auth/pages/AcceptInvitePage").then((m) => ({
    default: m.AcceptInvitePage,
  }))
);

// Feature chunks
const DatasetsPage = lazy(() =>
  import("../features/datasets/pages/DatasetsPage").then((m) => ({
    default: m.DatasetsPage || m.default,
  }))
);
const DatasetProfilePage = lazy(() =>
  import("../features/datasets/pages/DatasetProfilePage").then((m) => ({
    default: m.DatasetProfilePage || m.default,
  }))
);
const PlanReviewPage = lazy(() =>
  import("../features/plans/pages/PlanReviewPage").then((m) => ({
    default: m.PlanReviewPage || m.default,
  }))
);
const RunPage = lazy(() =>
  import("../features/runs/pages/RunPage").then((m) => ({
    default: m.RunPage || m.default,
  }))
);
const ModelSettingsPage = lazy(() =>
  import("../features/model-config/pages/ModelSettingsPage").then((m) => ({
    default: m.ModelSettingsPage || m.default,
  }))
);
const UsersPage = lazy(() =>
  import("../features/users/pages/UsersPage").then((m) => ({
    default: m.UsersPage || m.default,
  }))
);
const AuditPage = lazy(() =>
  import("../features/audit/pages/AuditPage").then((m) => ({
    default: m.AuditPage || m.default,
  }))
);
const EvaluationPage = lazy(() =>
  import("../features/evaluation/pages/EvaluationPage").then((m) => ({
    default: m.EvaluationPage || m.default,
  }))
);

// Error and status pages
const Forbidden = lazy(() =>
  import("../pages/Forbidden").then((m) => ({
    default: m.Forbidden || m.default,
  }))
);
const NotFound = lazy(() =>
  import("../pages/NotFound").then((m) => ({
    default: m.NotFound || m.default,
  }))
);

/**
 * Standard page suspense skeleton fallback.
 */
function PageSkeleton() {
  return (
    <div
      className="space-y-6 animate-pulse"
      role="status"
      aria-label="Loading page content…"
    >
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-48 rounded" />
        <Skeleton className="h-9 w-32 rounded" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Skeleton className="h-24 rounded-lg" />
        <Skeleton className="h-24 rounded-lg" />
        <Skeleton className="h-24 rounded-lg" />
        <Skeleton className="h-24 rounded-lg" />
      </div>
      <Skeleton className="h-96 rounded-lg w-full" />
    </div>
  );
}

/**
 * Route guard loader enforcing permission requirements before navigation completes.
 */
function requirePermissionLoader(perm: Permission) {
  return () => {
    const { accessToken, user } = useSessionStore.getState();
    if (!accessToken) {
      throw redirect("/login");
    }
    if (!user || !hasPermission(user.role, perm)) {
      throw redirect("/403");
    }
    return null;
  };
}

/**
 * Route guard wrapper component ensuring permissions are enforced even on in-memory updates.
 */
function RequirePermissionGuard({
  perm,
  children,
}: {
  perm: Permission;
  children: ReactNode;
}) {
  const { accessToken, user } = useSessionStore();

  if (!accessToken) {
    return <Navigate to="/login" replace />;
  }

  if (!user || !hasPermission(user.role, perm)) {
    return <Navigate to="/403" replace />;
  }

  return <Suspense fallback={<PageSkeleton />}>{children}</Suspense>;
}

/**
 * Root index redirector: sends authenticated users to their role landing route,
 * or unauthenticated visitors to /login.
 */
function RoleLandingRedirect() {
  const { accessToken, user } = useSessionStore();

  if (!accessToken || !user) {
    return <Navigate to="/login" replace />;
  }

  return <Navigate to={getRoleLandingRoute(user.role)} replace />;
}

export const router = createBrowserRouter([
  // Public routes
  {
    path: "/login",
    element: (
      <Suspense fallback={<PageSkeleton />}>
        <LoginPage />
      </Suspense>
    ),
  },
  {
    path: "/invite/:token",
    element: (
      <Suspense fallback={<PageSkeleton />}>
        <AcceptInvitePage />
      </Suspense>
    ),
  },

  // Protected application routes
  {
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      {
        path: "/",
        element: <RoleLandingRedirect />,
      },
      {
        path: "/datasets",
        loader: requirePermissionLoader("dataset.view"),
        element: (
          <RequirePermissionGuard perm="dataset.view">
            <DatasetsPage />
          </RequirePermissionGuard>
        ),
      },
      {
        path: "/datasets/:id",
        loader: requirePermissionLoader("profile.view"),
        element: (
          <RequirePermissionGuard perm="profile.view">
            <DatasetProfilePage />
          </RequirePermissionGuard>
        ),
      },
      {
        path: "/plans/:id",
        loader: requirePermissionLoader("profile.view"),
        element: (
          <RequirePermissionGuard perm="profile.view">
            <PlanReviewPage />
          </RequirePermissionGuard>
        ),
      },
      {
        path: "/plans/:id/run",
        loader: requirePermissionLoader("profile.view"),
        element: (
          <RequirePermissionGuard perm="profile.view">
            <RunPage />
          </RequirePermissionGuard>
        ),
      },
      {
        path: "/settings/model",
        loader: requirePermissionLoader("model.view"),
        element: (
          <RequirePermissionGuard perm="model.view">
            <ModelSettingsPage />
          </RequirePermissionGuard>
        ),
      },
      {
        path: "/settings/users",
        loader: requirePermissionLoader("users.view"),
        element: (
          <RequirePermissionGuard perm="users.view">
            <UsersPage />
          </RequirePermissionGuard>
        ),
      },
      {
        path: "/audit",
        loader: requirePermissionLoader("audit.view"),
        element: (
          <RequirePermissionGuard perm="audit.view">
            <AuditPage />
          </RequirePermissionGuard>
        ),
      },
      {
        path: "/evaluation",
        loader: requirePermissionLoader("evaluation.run"),
        element: (
          <RequirePermissionGuard perm="evaluation.run">
            <EvaluationPage />
          </RequirePermissionGuard>
        ),
      },
    ],
  },

  // Error pages
  {
    path: "/403",
    element: (
      <Suspense fallback={<PageSkeleton />}>
        <Forbidden />
      </Suspense>
    ),
  },
  {
    path: "*",
    element: (
      <Suspense fallback={<PageSkeleton />}>
        <NotFound />
      </Suspense>
    ),
  },
]);

export default router;
