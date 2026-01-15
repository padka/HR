import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("a11y: /slots has no critical violations", async ({ page }) => {
  await page.goto("/slots");
  const results = await new AxeBuilder({ page }).analyze();
  const critical = results.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious"
  );
  expect(critical).toEqual([]);
});

test("a11y: /candidates has no critical violations", async ({ page }) => {
  await page.goto("/candidates");
  const results = await new AxeBuilder({ page }).analyze();
  const critical = results.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious"
  );
  expect(critical).toEqual([]);
});
