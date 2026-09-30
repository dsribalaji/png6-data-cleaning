// Live UI walk-through against a running backend (not the stubbed e2e/ specs).
// Usage (backend + `npm run dev` running): BASE=http://localhost:5173 node scripts/live-walkthrough.mjs
import { chromium } from "@playwright/test";

const BASE = process.env.BASE ?? "http://localhost:5199";
const SHOTS = process.env.SHOTS ?? "/tmp";
const REF = process.env.FILE ?? new URL("../../data/reference/VendorInvoices_uncleaned.xlsx", import.meta.url).pathname;

const browser = await chromium.launch({ executablePath: process.env.CHROME ?? "/usr/bin/google-chrome" });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("response", (r) => {
  if (r.url().includes("/api/") && r.status() >= 400) errors.push(`${r.request().method()} ${r.url()} -> ${r.status()}`);
});
let n = 0;
const shot = async (label) => {
  await page.screenshot({ path: `${SHOTS}/${String(++n).padStart(2, "0")}-${label}.png`, fullPage: true });
  console.log(`[${n}] ${label}: ${page.url()}`);
};

try {
  await page.goto(`${BASE}/login`);
  await page.getByLabel("Work email").fill("engineer@example.com");
  await page.locator("input[type=password]").fill("Engineer123!");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/datasets/);
  await shot("datasets");

  await page.getByRole("button", { name: /upload/i }).first().click();
  await page.locator('input[type="file"]').setInputFiles(REF);
  const nameBox = page.getByLabel(/dataset name/i);
  if (await nameBox.count()) await nameBox.fill(`golden ${Date.now()}`);
  await shot("upload-modal");
  await page.getByRole("dialog").getByRole("button", { name: "Upload & profile" }).last().click();
  await page.getByRole("link", { name: /golden/i }).first().waitFor({ timeout: 240000 });
  await page.waitForTimeout(1500);
  await shot("datasets-after-upload");

  await page.getByRole("link", { name: /golden/i }).first().click();
  await page.getByRole("button", { name: "Generate plan" }).waitFor({ timeout: 240000 });
  await shot("profile");
  await page.getByRole("button", { name: "Generate plan" }).click();
  await page.waitForURL(/\/plans\//, { timeout: 240000 });
  await page.getByRole("button", { name: /Approve plan/ }).waitFor();
  await shot("plan-review");

  for (const radio of await page.getByRole("radio", { name: "Accept" }).all()) {
    if (!(await radio.isChecked())) await radio.check();
  }
  await page.waitForTimeout(1000);
  await shot("plan-decided");
  await page.getByRole("button", { name: /Approve plan/ }).click();
  await page.getByRole("button", { name: "Confirm" }).click();
  await page.waitForURL(/\/run/, { timeout: 240000 });
  await page.getByText(/154,?292/).first().waitFor({ timeout: 240000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await shot("run");

  for (const fmt of ["XLSX", "CSV", "Pipeline"]) {
    const btn = page.getByRole("button", { name: new RegExp(fmt, "i") }).first();
    const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 180000 }), btn.click()]);
    console.log(`export ${fmt}: ${dl.suggestedFilename()}`);
  }

  await page.getByRole("button", { name: /Roll back here/ }).last().click();
  await shot("rollback-modal");
  await page.getByRole("dialog").getByRole("textbox").fill("live UI check: restore the original file");
  await page.getByRole("dialog").getByRole("button", { name: /Roll back/ }).click();
  await page.waitForTimeout(3000);
  await shot("after-rollback");

  await page.reload();
  await page.waitForTimeout(2000);
  await shot("after-reload");
  await page.goto(`${BASE}/datasets`);
  await page.waitForTimeout(2000);
  await shot("audit");
} catch (e) {
  console.log("STOPPED:", e.message.split("\n")[0]);
  await shot("stopped");
} finally {
  console.log(errors.length ? `API/page errors:\n  ${errors.join("\n  ")}` : "no API/page errors");
  await browser.close();
}
