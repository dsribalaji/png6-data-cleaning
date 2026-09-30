import { expect, test } from "@playwright/test";
import {
  E2E_PASSWORD,
  E2E_WRONG_PASSWORD,
  signIn,
  stubApi,
} from "./support/api-stub";

test.describe("sign-in", () => {
  test("valid credentials land the engineer on the dataset list", async ({ page }) => {
    const api = await stubApi(page, { role: "data_engineer" });

    await page.goto("/login");
    await signIn(page, E2E_PASSWORD);

    await expect(page).toHaveURL(/\/datasets$/);
    await expect(page.getByRole("heading", { level: 1, name: "Datasets" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Vendor invoices" })).toBeVisible();
    expect(api.calls).toContain("POST /auth/login");
    expect(api.unhandled).toEqual([]);
  });

  test("a wrong password shows the canonical error and keeps the user on the form", async ({ page }) => {
    await stubApi(page, { role: "data_engineer" });

    await page.goto("/login");
    await page.getByLabel(/work email/i).fill("engineer@example.com");
    await page.getByLabel(/password/i).fill(E2E_WRONG_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page.getByRole("alert")).toHaveText("Email or password is incorrect.");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
  });

  test("/login?expired=1 explains that the session expired", async ({ page }) => {
    await stubApi(page, { role: "data_engineer", rejectSignIn: true });

    await page.goto("/login?expired=1");

    await expect(page.getByRole("alert")).toHaveText(
      "Your session expired. Please sign in again."
    );
  });

  test("each role is sent to its own landing page", async ({ page }) => {
    await stubApi(page, { role: "administrator" });

    await page.goto("/login");
    await signIn(page);

    await expect(page).toHaveURL(/\/settings\/model$/);
    await expect(
      page.getByRole("heading", { level: 1, name: "Model settings" })
    ).toBeVisible();
  });
});
