import { test, expect } from "@playwright/test";

test.describe("/app/candidates", () => {
  test("renders list view", async ({ page }) => {
    await page.goto("/app/candidates");
    await page.waitForLoadState("networkidle");

    // Wait for lazy loading
    await page.waitForTimeout(500);

    // Check for table or card list
    await expect(page.locator("table, [data-view]")).toBeVisible({ timeout: 10000 });
  });

  test("has view mode switcher", async ({ page }) => {
    await page.goto("/app/candidates");
    await page.waitForLoadState("networkidle");

    // Should have view mode buttons (list/kanban/calendar)
    const viewButtons = page.locator("button").filter({ hasText: /список|kanban|календарь/i });
    await expect(viewButtons.first()).toBeVisible({ timeout: 10000 });
  });

  test("can navigate to new candidate form", async ({ page }) => {
    await page.goto("/app/candidates");
    await page.waitForLoadState("networkidle");

    const newButton = page.locator("a[href*='new'], button").filter({ hasText: /создать|добавить|новый/i });
    if (await newButton.count() > 0) {
      await newButton.first().click();
      await page.waitForURL("/app/candidates/new");
    }
  });
});
