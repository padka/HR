import { test, expect } from "@playwright/test";

test.describe("/candidates", () => {
  test("renders list", async ({ page }) => {
    await page.goto("/candidates");
    await expect(page.locator("table, [data-list]")).toBeVisible();
  });

  test("visual snapshot: candidates", async ({ page }) => {
    await page.goto("/candidates");
    await expect(page).toHaveScreenshot("candidates-fold.png", { maxDiffPixelRatio: 0.02 });
  });
});
