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

  test("has view mode switcher", async ({ page }) => {
    await page.goto("/app/candidates");
    await page.waitForLoadState("domcontentloaded");

    const viewSwitcher = page.getByTestId("candidates-view-switcher");
    await expect(viewSwitcher).toBeVisible({ timeout: 10000 });
    await expect(viewSwitcher.getByRole("button").first()).toBeVisible({ timeout: 10000 });
  });

  test("can navigate to new candidate form", async ({ page }) => {
    await page.goto("/app/candidates");
    await page.waitForLoadState("domcontentloaded");

    const newButton = page.getByTestId("candidates-create-btn");
    await expect(newButton).toBeVisible({ timeout: 10000 });
    await newButton.click();
    await page.waitForURL("/app/candidates/new");
  });
});
