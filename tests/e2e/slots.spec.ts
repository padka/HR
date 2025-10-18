import { test, expect } from "@playwright/test";

test.describe("/slots", () => {
  test("renders header + table", async ({ page }) => {
    await page.goto("/slots");
    await expect(page.locator("table thead")).toBeVisible();
  });

  test("visual snapshot: table above the fold", async ({ page }) => {
    await page.goto("/slots");
    await page.waitForSelector("table thead");
    await expect(page).toHaveScreenshot("slots-fold.png", { maxDiffPixelRatio: 0.02 });
  });
});
