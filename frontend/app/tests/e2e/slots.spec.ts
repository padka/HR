import { test, expect } from "@playwright/test";

test.describe("/app/slots", () => {
  test("renders slots list", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    await expect(page.getByRole("heading", { name: "Слоты", exact: false })).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId("slots-filter-bar")).toBeVisible({ timeout: 10000 });

    // Check for table or empty state if data loaded
    const table = page.getByTestId("slots-table");
    const empty = page.getByTestId("slots-empty-state");
    await expect(table.or(empty).first()).toBeVisible({ timeout: 10000 });
  });

  test("has status filter chips", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("domcontentloaded");

    const summary = page.getByRole("group", { name: /Сводка слотов/i });
    await expect(summary).toBeVisible({ timeout: 10000 });
    await expect(summary.getByRole("button", { name: /Свободные/i }).first()).toBeVisible({ timeout: 10000 });
  });

  test("can navigate to create slots", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("domcontentloaded");

    const createButton = page.getByTestId("slots-create-btn");
    await expect(createButton).toBeVisible({ timeout: 10000 });
    await createButton.click();
    await page.waitForURL("/app/slots/create");
  });
});
