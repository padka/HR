import { test, expect } from "@playwright/test";

test.describe("/app/candidates", () => {
  test("renders list view", async ({ page }) => {
    await page.goto("/app/candidates");
    await page.waitForLoadState("networkidle");

    // Wait for lazy loading
    await page.waitForTimeout(500);

    await expect(page.getByRole("heading", { name: "Кандидаты", exact: false })).toBeVisible({ timeout: 10000 });

    // Check for table or empty state
    const listOrEmpty = page.locator("table.data-table, .empty-state").first();
    await expect(listOrEmpty).toBeVisible({ timeout: 10000 });
  });

  test("has view mode switcher", async ({ page }) => {
    await page.goto("/app/candidates");
    await page.waitForLoadState("networkidle");

    // Should have view mode buttons (list/kanban/calendar)
    const viewButtons = page.locator("button").filter({ hasText: /список|канбан|календарь/i });
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
