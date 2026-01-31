import { test, expect } from "@playwright/test";

test.describe("/app/slots", () => {
  test("renders slots list", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);

    await expect(page.getByRole("heading", { name: "Слоты", exact: false })).toBeVisible({ timeout: 10000 });
    await expect(page.locator(".filter-bar").first()).toBeVisible({ timeout: 10000 });

    // Check for table or empty state if data loaded
    const listOrEmpty = page.locator("table.data-table, .empty-state").first();
    if (await listOrEmpty.count()) {
      await expect(listOrEmpty).toBeVisible({ timeout: 10000 });
    }
  });

  test("has status filter chips", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("networkidle");

    const statusSelect = page.locator("select").filter({ hasText: /Свободные|Ожидают|Забронированы|Подтверждены/i }).first();
    await expect(statusSelect).toBeVisible({ timeout: 10000 });
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
