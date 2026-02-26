import { test, expect } from "@playwright/test";

test.describe("/app/cities focus and navigation", () => {
  test("can navigate to city edit from list", async ({ page }) => {
    await page.goto("/app/cities");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    // Find a city edit link
    const cityLink = page.getByTestId("city-edit-link").first();
    if (await cityLink.count() > 0) {
      await cityLink.click();
      await page.waitForURL(/\/app\/cities\/\d+\/edit/);
    }
  });

  test("can navigate to new city form", async ({ page }) => {
    await page.goto("/app/cities");
    await page.waitForLoadState("domcontentloaded");

    const newButton = page.getByTestId("cities-create-btn");
    await expect(newButton).toBeVisible({ timeout: 10000 });
    await newButton.click();
    await page.waitForURL("/app/cities/new");
  });

  test("city form has timezone input", async ({ page }) => {
    await page.goto("/app/cities/new");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    // Check for timezone select
    await expect(page.getByTestId("city-tz-input")).toBeVisible({ timeout: 10000 });
  });
});
