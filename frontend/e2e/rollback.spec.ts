import { expect, test } from "@playwright/test";
import {
  PLAN_ID,
  ROLLBACK_REASON,
  gotoInApp,
  signIn,
  stubApi,
} from "./support/api-stub";

/**
 * PRD Section 7, S6: rolling back is only offered for versions that are not the
 * live output, the reason has to clear the client-side minimum, and the modal
 * must survive a failed submit.
 */
test("a rollback needs a reason of at least 10 characters", async ({ page }) => {
  const api = await stubApi(page, { role: "data_engineer" });

  await page.goto("/login");
  await signIn(page);
  await gotoInApp(page, `/plans/${PLAN_ID}/run`);

  await expect(page.getByRole("heading", { level: 1, name: /^Run/ })).toBeVisible();

  // v2 is the live output, so the older versions carry the rollback action.
  await page.getByRole("button", { name: "Roll back here" }).first().click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(/Roll back to v/)).toBeVisible();

  await dialog.getByLabel(/reason/i).fill("short");
  await dialog.getByRole("button", { name: "Roll back" }).click();

  await expect(dialog.getByRole("alert")).toHaveText(
    "Enter a reason of at least 10 characters."
  );
  expect(api.calls).not.toContain(`POST /plans/${PLAN_ID}/rollback`);

  // The failed submit must not close or clear the form.
  await expect(dialog.getByLabel(/reason/i)).toHaveValue("short");

  await dialog.getByLabel(/reason/i).fill(ROLLBACK_REASON);
  await dialog.getByRole("button", { name: "Roll back" }).click();

  await expect.poll(() => api.calls).toContain(`POST /plans/${PLAN_ID}/rollback`);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(api.unhandled).toEqual([]);
});

test("the reason counter resets when the modal is reopened", async ({ page }) => {
  await stubApi(page, { role: "data_engineer" });

  await page.goto("/login");
  await signIn(page);
  await gotoInApp(page, `/plans/${PLAN_ID}/run`);

  await expect(page.getByRole("heading", { level: 1, name: /^Run/ })).toBeVisible();
  await page.getByRole("button", { name: "Roll back here" }).first().click();

  const dialog = page.getByRole("dialog");
  await dialog.getByLabel(/reason/i).fill(ROLLBACK_REASON);
  await expect(dialog.getByText(`${ROLLBACK_REASON.length}/500`)).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await page.getByRole("button", { name: "Roll back here" }).first().click();
  await expect(page.getByLabel(/reason/i)).toHaveValue("");
});

test("auditors cannot roll back", async ({ page }) => {
  await stubApi(page, { role: "auditor" });

  await page.goto("/login");
  await signIn(page);
  await gotoInApp(page, `/plans/${PLAN_ID}/run`);

  // Read-only: the page renders, but no rollback action is offered.
  await expect(page.getByRole("heading", { level: 1, name: /^Run/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Roll back here" })).toHaveCount(0);
});
