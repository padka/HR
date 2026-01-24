import { test, expect } from "@playwright/test";

test.describe("/app/slots", () => {
  test("renders slots list", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);

    // Check for table or cards view
    await expect(page.locator("table, .slot-grid, [data-view]").first()).toBeVisible({ timeout: 10000 });
  });

  test("has status filter chips", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("networkidle");

    // Should have status filter buttons
    const statusFilters = page.locator("button, .chip").filter({ hasText: /все|free|booked|pending/i });
    await expect(statusFilters.first()).toBeVisible({ timeout: 10000 });
  });

  test("can navigate to create slots", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("networkidle");

    const createButton = page.locator("a[href*='create'], button").filter({ hasText: /создать/i });
    if (await createButton.count() > 0) {
      await createButton.first().click();
      await page.waitForURL("/app/slots/create");
    }
  });
});
