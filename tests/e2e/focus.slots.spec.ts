import { test, expect } from "@playwright/test";
import { pressTab, pressShiftTab, pressEsc } from "./utils/keyboard";

test.describe("/slots focus trap", () => {
  test("sheet opens, traps focus, ESC closes and restores focus", async ({ page }) => {
    await page.goto("/slots");

    // Найдём кнопку, которая открывает sheet/drawer. Пробуем несколько селекторов:
    const openers = [
      '[data-test="open-slots-sheet"]',
      '[data-testid="open-slots-sheet"]',
      'button[aria-controls*="sheet"], [data-sheet-open]',
      'button:has-text("Новый слот"), button:has-text("Фильтры"), [role="button"]:has-text("Фильтры")'
    ];
    let opener = null;
    for (const sel of openers) {
      const el = page.locator(sel).first();
      if (await el.count()) { opener = el; break; }
    }
    expect(opener, "Не найден триггер открытия sheet на /slots").toBeTruthy();

    const openerHandle = await opener!.elementHandle();
    await opener!.focus();
    await opener!.press("Enter");

    // Ожидаем диалог (ARIA). Пробуем role=dialog и data-атрибуты:
    const dialog = page.locator('[role="dialog"][aria-modal="true"], [data-sheet], .sheet, .drawer').first();
    await expect(dialog, "Sheet не появился").toBeVisible();

    // Первый фокусируемый элемент внутри диалога — в фокусе
    const firstFocusable = dialog.locator('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])').first();
    await expect(firstFocusable).toBeFocused();

    // Прокрутим Tab несколько раз и убедимся, что фокус не выскакивает наружу
    await pressTab(page, 5);
    const anyOutsideFocused = page.locator("body > *:not([role='dialog']) *:focus").first();
    expect(await anyOutsideFocused.count(), "Фокус ушёл за пределы диалога при Tab").toBe(0);

    // Shift+Tab назад — фокус остаётся внутри диалога
    await pressShiftTab(page, 5);
    expect(await anyOutsideFocused.count(), "Фокус ушёл за пределы диалога при Shift+Tab").toBe(0);

    // Закрываем ESC
    await pressEsc(page);
    await expect(dialog).toBeHidden();

    // Фокус вернулся на исходный триггер
    const active = await page.evaluateHandle(() => document.activeElement);
    expect(await openerHandle!.evaluate((n, a) => n === a, active)).toBeTruthy();
  });
});
