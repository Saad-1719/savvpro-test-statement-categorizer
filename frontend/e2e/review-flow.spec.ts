// The real thing: upload a sample statement, clear every Needs Review group, set the phone bill's
// business-use %, check the totals turn Final, and download the export.
import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const SAMPLE_DATA = path.join(__dirname, "..", "..", "sample_data");

async function loadDemoStatement(page: Page, format: "CSV" | "PDF") {
  await page.goto("/");
  await page.getByRole("button", { name: `Try Demo statement ${format}` }).click();
  await expect(page.getByText(`first_federal_checking_2025.${format.toLowerCase()}`)).toBeVisible();
}

test("a driver can review every unsure row, finish the totals and export them", async ({ page }) => {
  await loadDemoStatement(page, "CSV");
  await expect(page.getByText("30 rows", { exact: false }).first()).toBeVisible();

  // Fix review groups one at a time until none are left. Each Apply sends one bulk request.
  const reviewItems = page.locator("section").filter({ hasText: /^Needs review:/ }).locator("li");
  for (let i = 0; i < 20 && (await reviewItems.count()) > 0; i++) {
    const item = reviewItems.first();
    await item.getByRole("combobox").selectOption("Personal");
    await item.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Saving…" })).toHaveCount(0);
  }
  await expect(page.getByText("Nothing left to review. Every row has a category.")).toBeVisible();

  // The phone bill still needs a business-use % before the totals can be final.
  await page.getByLabel(/Business-use percent for VERIZON/).fill("60");
  await page.getByLabel(/Business-use percent for VERIZON/).press("Enter");

  const totals = page.locator("section").filter({ has: page.getByRole("heading", { name: "Totals" }) });
  await expect(totals.getByText("Final", { exact: true })).toBeVisible();
  await expect(totals.getByText("Deductible: $51.00")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await totals.getByRole("link", { name: /export csv/i }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("categorized_2025.csv");
});

test("the PDF version of the statement gives the same rows", async ({ page }) => {
  await loadDemoStatement(page, "PDF");
  const table = page.getByRole("table");
  await expect(table.getByRole("row")).toHaveCount(31); // header + 30 rows
  await expect(table.getByText("SAFEWAY FUEL 1187")).toBeVisible();
});

test("a statement in an unknown layout is refused with a clear message", async ({ page }) => {
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles(path.join(SAMPLE_DATA, "broken", "unknown_layout.csv"));
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Unrecognized statement layout");
});

test("the decision details open from the keyboard", async ({ page }) => {
  await loadDemoStatement(page, "CSV");
  const badge = page.getByRole("row", { name: /SAFEWAY FUEL 1187/ }).getByRole("button", { name: /show why/ });
  await badge.focus();
  await page.keyboard.press("Enter");
  await expect(badge).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByText("Evidence found")).toBeVisible();
});
