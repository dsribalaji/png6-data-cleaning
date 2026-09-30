import { expect, test } from "@playwright/test";
import { gotoInApp, signIn, stubApi, type StubRole } from "./support/api-stub";

/**
 * PRD Section 4 (role table) enforced by the router: a role that lacks the
 * route permission never reaches the page, it lands on /403 with the canonical
 * copy. The per-permission matrix itself is covered by
 * `src/auth/permissions.test.ts`; this spec proves the router honours it.
 */
interface RouteCase {
  path: string;
  heading: RegExp;
}

const ROUTES: Record<string, RouteCase> = {
  datasets: { path: "/datasets", heading: /^Datasets$/ },
  profile: { path: "/datasets/dataset-1", heading: /^Vendor invoices/ },
  plan: { path: "/plans/plan-1", heading: /^Plan review$/ },
  run: { path: "/plans/plan-1/run", heading: /^Run/ },
  model: { path: "/settings/model", heading: /^Model settings$/ },
  users: { path: "/settings/users", heading: /^Users & roles$/ },
  audit: { path: "/audit", heading: /^Audit trail$/ },
  evaluation: { path: "/evaluation", heading: /^Evaluation$/ },
};

/**
 * `viewer` is left out on purpose: its route permissions are identical to the
 * engineer's, and src/auth/permissions.test.ts covers the full matrix
 * (including the viewer) at the unit level.
 */
const MATRIX: Record<Exclude<StubRole, "viewer">, { allowed: string[]; denied: string[] }> = {
  data_engineer: {
    allowed: ["datasets", "profile", "plan", "run"],
    denied: ["model", "users", "audit", "evaluation"],
  },
  administrator: {
    allowed: ["datasets", "profile", "plan", "run", "model", "users", "audit", "evaluation"],
    denied: [],
  },
  auditor: {
    allowed: ["datasets", "profile", "plan", "run", "audit", "evaluation"],
    denied: ["model", "users"],
  },
};

const ROLES: Array<Exclude<StubRole, "viewer">> = [
  "data_engineer",
  "administrator",
  "auditor",
];

for (const role of ROLES) {
  const matrix = MATRIX[role];

  for (const key of matrix.allowed) {
    const route = ROUTES[key];

    test(`${role} can open ${route.path}`, async ({ page }) => {
      await stubApi(page, { role });
      await page.goto("/login");
      await signIn(page);
      await gotoInApp(page, route.path);

      await expect(page.getByRole("heading", { level: 1, name: route.heading })).toBeVisible();
      await expect(page).not.toHaveURL(/\/403$/);
    });
  }

  for (const key of matrix.denied) {
    const route = ROUTES[key];

    test(`${role} is redirected away from ${route.path}`, async ({ page }) => {
      const api = await stubApi(page, { role });
      await page.goto("/login");
      await signIn(page);
      await gotoInApp(page, route.path);

      await expect(page).toHaveURL(/\/403$/);
      await expect(page.getByRole("heading", { level: 1, name: "403 Forbidden" })).toBeVisible();
      await expect(
        page.getByText("You don't have access to this page.")
      ).toBeVisible();
      // The denied page must not have been fetched either.
      expect(api.unhandled).toEqual([]);
    });
  }
}
