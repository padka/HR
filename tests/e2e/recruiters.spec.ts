import { test, expect } from "@playwright/test";

test.describe("/recruiters", () => {
  test("renders list", async ({ page }) => {
    await page.goto("/recruiters");
    await expect(page.locator("table, [data-list]")).toBeVisible();
  });

  test("visual snapshot: recruiters", async ({ page }) => {
    await page.goto("/recruiters");
    await expect(page).toHaveScreenshot("recruiters-fold.png", { maxDiffPixelRatio: 0.02 });
  });
});
