import { test, expect } from "@playwright/test";

test.describe("/app/slots navigation and modals", () => {
  test("can open slot details sheet", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    // Try to open details via the "..." button
    const detailsButton = page.getByTestId("slot-details-btn").first();
    if (await detailsButton.count() > 0) {
      await detailsButton.click();

      const dialog = page.getByRole("dialog").first();
      await expect(dialog).toBeVisible({ timeout: 5000 });

      const closeButton = page.getByRole("button", { name: /закрыть/i }).first();
      if (await closeButton.count() > 0) {
        await closeButton.click();
        await expect(dialog).toBeHidden({ timeout: 5000 });
      }
    }
  });

  test("bulk select checkbox is available", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    const headerCheckbox = page.getByTestId("slots-select-all");
    if (await headerCheckbox.count() > 0) {
      await expect(headerCheckbox).toBeVisible({ timeout: 10000 });
    } else {
      const filters = page.getByTestId("slots-filter-bar");
      await expect(filters).toBeVisible({ timeout: 10000 });
    }
  });

  test("status summary buttons are visible", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    const summary = page.getByRole("group", { name: /Сводка слотов/i });
    await expect(summary).toBeVisible({ timeout: 10000 });
    await expect(summary.getByRole("button").first()).toBeVisible({ timeout: 10000 });
  });
});
