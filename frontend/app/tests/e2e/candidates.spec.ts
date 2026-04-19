import { test, expect } from "@playwright/test";

test.describe("/app/candidates", () => {
  test("renders list view", async ({ page }) => {
    await page.goto("/app/candidates");
    await page.waitForLoadState("domcontentloaded");

    // Wait for lazy loading
    await page.waitForTimeout(500);

    await expect(page.getByRole("heading", { name: "Кандидаты", exact: false })).toBeVisible({ timeout: 10000 });

    // Check for table or empty state
    const table = page.getByTestId("candidates-table");
    const empty = page.getByTestId("candidates-empty-state");
    await expect(table.or(empty).first()).toBeVisible({ timeout: 10000 });
  });

  test("renders filter bar without view switcher", async ({ page }) => {
    await page.goto("/app/candidates");
    await page.waitForLoadState("domcontentloaded");

    await expect(page.getByTestId("candidates-filter-bar")).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId("candidates-view-switcher")).toHaveCount(0);
  });

  test("new candidate form remains reachable directly", async ({ page }) => {
    await page.goto("/app/candidates/new");
    await page.waitForLoadState("domcontentloaded");

    await expect(page.getByRole("heading", { name: "Новый кандидат", exact: false })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("link", { name: "← К списку" })).toBeVisible({ timeout: 10000 });
  });
});
