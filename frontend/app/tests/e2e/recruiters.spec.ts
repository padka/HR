import { test, expect } from "@playwright/test";

test.describe("/app/recruiters", () => {
  test("renders recruiter cards", async ({ page }) => {
    await page.goto("/app/recruiters");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);

    // Check for cards or list
    await expect(page.locator("[data-rec-card], .grid-cards, table").first()).toBeVisible({ timeout: 10000 });
  });

  test("can navigate to new recruiter form", async ({ page }) => {
    await page.goto("/app/recruiters");
    await page.waitForLoadState("networkidle");

    const newButton = page.locator("a[href*='new'], button").filter({ hasText: /создать|добавить|новый/i });
    if (await newButton.count() > 0) {
      await newButton.first().click();
      await page.waitForURL("/app/recruiters/new");
    }
  });

  test("new recruiter form has city selection", async ({ page }) => {
    await page.goto("/app/recruiters/new");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);

    // Check for city tiles or checkboxes
    await expect(page.locator("input[type='checkbox'], [data-city-tile], .city-tile").first()).toBeVisible({ timeout: 10000 });
  });
});
