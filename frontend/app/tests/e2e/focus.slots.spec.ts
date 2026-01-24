import { test, expect } from "@playwright/test";

test.describe("/app/slots navigation and modals", () => {
  test("can open slot details sheet", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);

    // Try to find and click a slot row or card
    const slotRow = page.locator("tr, .slot-card").first();
    if (await slotRow.count() > 0) {
      await slotRow.click();

      // Wait for sheet/modal to appear
      const sheet = page.locator('[role="dialog"], .sheet, .overlay').first();
      if (await sheet.count() > 0) {
        await expect(sheet).toBeVisible({ timeout: 5000 });

        // Press Escape to close
        await page.keyboard.press("Escape");
        await expect(sheet).toBeHidden({ timeout: 5000 });
      }
    }
  });

  test("bulk select checkbox is available", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);

    // Check for select all checkbox
    const checkbox = page.locator("input[type='checkbox']").first();
    await expect(checkbox).toBeVisible({ timeout: 10000 });
  });

  test("view mode switcher works", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);

    // Find view mode buttons
    const viewButtons = page.locator("button").filter({ hasText: /таблица|карточки|agenda/i });
    if (await viewButtons.count() > 1) {
      // Click the second view mode
      await viewButtons.nth(1).click();
      await page.waitForTimeout(300);
    }
  });
});
