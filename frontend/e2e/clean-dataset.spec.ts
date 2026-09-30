import { expect, test } from "@playwright/test";
import {
  NEW_DATASET_NAME,
  UPLOAD_FILE,
  gotoInApp,
  signIn,
  stubApi,
} from "./support/api-stub";

/**
 * PRD Section 6/7: the whole happy path in one pass — upload, profile, generate
 * the plan (SSE), approve every step, run the plan, export the cleaned file.
 */
test("upload → generate plan → approve → run → export", async ({ page }) => {
  const api = await stubApi(page, { role: "data_engineer" });

  await page.goto("/login");
  await signIn(page);
  await expect(page.getByRole("heading", { level: 1, name: "Datasets" })).toBeVisible();

  // 1. Upload the uncleaned workbook (PRD S3).
  await page.getByRole("button", { name: "Upload dataset" }).click();
  const uploadDialog = page.getByRole("dialog");
  await expect(uploadDialog).toBeVisible();
  await uploadDialog.locator('input[type="file"]').setInputFiles(UPLOAD_FILE);
  await uploadDialog.getByLabel(/dataset name/i).fill(NEW_DATASET_NAME);
  // The form also carries a screen-reader-only submit button with the same
  // label for Enter-key submits, so the footer's action is the last match.
  await uploadDialog.getByRole("button", { name: "Upload & profile" }).last().click();

  await expect(uploadDialog).toHaveCount(0);
  const datasetLink = page.getByRole("link", { name: NEW_DATASET_NAME });
  await expect(datasetLink).toBeVisible();
  expect(api.calls).toContain("POST /datasets");

  // 2. Profile page, then generate the plan. The page leaves for the plan only
  //    when the SSE stream reports PlanGenerated.
  await datasetLink.click();
  await expect(page).toHaveURL(/\/datasets\/dataset-1$/);
  await expect(page.getByRole("heading", { level: 1, name: new RegExp(NEW_DATASET_NAME) })).toBeVisible();

  await page.getByRole("button", { name: "Generate plan" }).click();
  await expect(page).toHaveURL(/\/plans\/plan-1$/);
  expect(api.calls).toContain("POST /datasets/dataset-1/plans");
  expect(api.calls).toContain("GET /datasets/dataset-1/events");

  // 3. Plan review: both steps are pre-accepted, so one click approves them.
  await expect(page.getByRole("heading", { level: 1, name: "Plan review" })).toBeVisible();
  const stepTable = page.getByRole("table");
  // The Operation column shows each step's summary (see describeStep).
  await expect(
    stepTable.getByRole("button", { name: "Standardise the format of vendor_name" })
  ).toBeVisible();
  await expect(
    stepTable.getByRole("button", { name: "Fill missing values in total using the median" })
  ).toBeVisible();

  await page.getByRole("button", { name: "Approve plan (2 of 2 decided)" }).click();
  const confirmDialog = page.getByRole("dialog");
  await expect(confirmDialog).toBeVisible();
  await expect(
    confirmDialog.getByText("Approve 2 steps? Unit and integration tests will be generated.")
  ).toBeVisible();
  await confirmDialog.getByRole("button", { name: "Confirm" }).click();

  // 4. The run page reports the validation results and unlocks the exports.
  await expect(page).toHaveURL(/\/plans\/plan-1\/run$/);
  await expect(page.getByRole("heading", { level: 1, name: /^Run/ })).toBeVisible();
  await expect(page.getByText("Tests passed", { exact: true })).toBeVisible();

  const exportButton = page.getByRole("button", { name: "CSV" });
  await expect(exportButton).toBeEnabled();
  await exportButton.click();

  await expect.poll(() => api.calls).toContain("POST /plans/plan-1/exports");
  await expect.poll(() => api.calls).toContain("GET /plans/plan-1/exports/download.csv");
  expect(api.unhandled).toEqual([]);
});

test("the export buttons unlock once the validation report passes", async ({ page }) => {
  await stubApi(page, { role: "data_engineer" });

  await page.goto("/login");
  await signIn(page);
  await gotoInApp(page, "/plans/plan-1/run");

  await expect(page.getByRole("heading", { level: 1, name: /^Run/ })).toBeVisible();
  // The stubbed report has allPassed: true, so the exports are offered.
  await expect(page.getByRole("button", { name: "XLSX" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Pipeline (JSON)" })).toBeEnabled();
});
