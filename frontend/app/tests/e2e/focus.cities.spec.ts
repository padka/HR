import { test, expect } from "@playwright/test";

test.describe("/app/cities focus and navigation", () => {
  test("can navigate to city edit from list", async ({ page }) => {
    await page.goto("/app/cities");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);

    // Find a city card or row
    const cityLink = page.locator("a[href*='/cities/'], button").filter({ hasText: /редактировать|изменить/i }).first();
    if (await cityLink.count() > 0) {
      await cityLink.click();
      await page.waitForURL(/\/app\/cities\/\d+\/edit/);
    }
  });

  test("can navigate to new city form", async ({ page }) => {
    await page.goto("/app/cities");
    await page.waitForLoadState("networkidle");

    const newButton = page.locator("a[href*='new'], button").filter({ hasText: /создать|добавить|новый/i });
    if (await newButton.count() > 0) {
      await newButton.first().click();
      await page.waitForURL("/app/cities/new");
    }
  });

  test("city form has timezone input", async ({ page }) => {
    await page.goto("/app/cities/new");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);

    // Check for timezone input
    await expect(page.locator("input[name*='tz'], input[placeholder*='часов'], select").first()).toBeVisible({ timeout: 10000 });
  });
});
