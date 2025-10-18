import { test, expect } from "@playwright/test";
import { pressTab, pressShiftTab, pressEsc } from "./utils/keyboard";

test.describe("/cities focus trap", () => {
  test("sheet focus trap and ESC behavior", async ({ page }) => {
    await page.goto("/cities");

    const openers = [
      '[data-test="open-cities-sheet"]',
      '[data-testid="open-cities-sheet"]',
      'button[aria-controls*="sheet"], [data-sheet-open]',
      'button:has-text("Добавить город"), button:has-text("Фильтры")'
    ];
    let opener = null;
    for (const sel of openers) {
      const el = page.locator(sel).first();
      if (await el.count()) { opener = el; break; }
    }
    expect(opener, "Не найден триггер открытия sheet на /cities").toBeTruthy();

    const openerHandle = await opener!.elementHandle();
    await opener!.focus();
    await opener!.press("Enter");

    const dialog = page.locator('[role="dialog"][aria-modal="true"], [data-sheet], .sheet, .drawer').first();
    await expect(dialog).toBeVisible();

    const firstFocusable = dialog.locator('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])').first();
    await expect(firstFocusable).toBeFocused();

    await pressTab(page, 5);
    const anyOutsideFocused = page.locator("body > *:not([role='dialog']) *:focus").first();
    expect(await anyOutsideFocused.count()).toBe(0);

    await pressShiftTab(page, 5);
    expect(await anyOutsideFocused.count()).toBe(0);

    await pressEsc(page);
    await expect(dialog).toBeHidden();

    const active = await page.evaluateHandle(() => document.activeElement);
    expect(await openerHandle!.evaluate((n, a) => n === a, active)).toBeTruthy();
  });
});
