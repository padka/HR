import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("a11y: /app/slots has no critical violations", async ({ page }) => {
  await page.goto("/app/slots");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(500);

  const results = await new AxeBuilder({ page }).analyze();
  const critical = results.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious"
  );
  expect(critical).toEqual([]);
});

test("a11y: /app/candidates has no critical violations", async ({ page }) => {
  await page.goto("/app/candidates");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(500);

  const results = await new AxeBuilder({ page }).analyze();
  const critical = results.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious"
  );
  expect(critical).toEqual([]);
});

test("a11y: /app/dashboard has no critical violations", async ({ page }) => {
  await page.goto("/app/dashboard");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(500);

  const results = await new AxeBuilder({ page }).analyze();
  const critical = results.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious"
  );
  expect(critical).toEqual([]);
});
