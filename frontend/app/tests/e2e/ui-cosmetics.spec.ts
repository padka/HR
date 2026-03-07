import { test, expect, type Page } from "@playwright/test";

async function expectNoHorizontalOverflow(page: Page) {
  const hasOverflow = await page.evaluate(() => {
    const root = document.documentElement;
    return root.scrollWidth > root.clientWidth + 1;
  });
  expect(hasOverflow).toBeFalsy();
}

async function openFirstCandidateDetail(page: Page) {
  await page.goto("/app/candidates");
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(500);

  const detailLink = page.locator('a[href^="/app/candidates/"]:not([href="/app/candidates/new"])').first();
  await expect(detailLink).toBeVisible({ timeout: 10000 });
  await detailLink.click();
  await expect(page.getByTestId("candidate-header")).toBeVisible({ timeout: 10000 });
}

test.describe("ui cosmetics smoke (desktop)", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("dashboard renders fullscreen incoming workspace", async ({ page }) => {
    await page.goto("/app/dashboard");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    await expect(page.locator(".background-scene")).toHaveCount(1);
    await expect(page.locator(".background-scene")).toBeVisible();

    const expandedIncoming = page.getByTestId("incoming-filter-bar");
    if (await expandedIncoming.count()) {
      await expect(expandedIncoming).toBeVisible({ timeout: 10000 });
      return;
    }

    const incomingSurface = page.getByTestId("dashboard-incoming-fullscreen");
    if (await incomingSurface.count()) {
      await expect(incomingSurface).toBeVisible({ timeout: 10000 });
      return;
    }
    await expect(page.getByText("Общая сводка")).toBeVisible({ timeout: 10000 });
  });

  test("candidates route uses quiet shell and keeps primary anchors visible", async ({ page }) => {
    await page.goto("/app/candidates");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    await expect(page.getByRole("heading", { name: "Кандидаты" })).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId("candidates-filter-bar")).toBeVisible({ timeout: 10000 });
    await expect(page.locator(".background-scene")).toHaveCount(0);
  });

  test("incoming page keeps expected visual anchors", async ({ page }) => {
    await page.goto("/app/incoming");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    await expect(page.getByTestId("incoming-filter-bar")).toBeVisible({ timeout: 10000 });
    const incomingCard = page.getByTestId("incoming-card").first();
    const incomingEmpty = page.getByTestId("incoming-empty-state");
    await expect(incomingCard.or(incomingEmpty).first()).toBeVisible({ timeout: 10000 });

    const proposeBtn = page.getByRole("button", { name: /предложить время/i }).first();
    if (await proposeBtn.count()) {
      await proposeBtn.click();
      await expect(page.getByTestId("incoming-schedule-modal")).toBeVisible({ timeout: 10000 });
      await page.getByRole("button", { name: /закрыть/i }).first().click();
      await expect(page.getByTestId("incoming-schedule-modal")).toBeHidden({ timeout: 10000 });
    }
  });

  test("slots page renders filters/table and opens booking or reschedule modal", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    await expect(page.getByTestId("slots-filter-bar")).toBeVisible({ timeout: 10000 });
    const slotsTable = page.getByTestId("slots-table");
    const slotsEmpty = page.getByTestId("slots-empty-state");
    await expect(slotsTable.or(slotsEmpty).first()).toBeVisible({ timeout: 10000 });

    const assignBtn = page.getByRole("button", { name: /^назначить$/i }).first();
    const rescheduleBtn = page.getByRole("button", { name: /^перенести$/i }).first();

    if (await assignBtn.count()) {
      await assignBtn.click();
      await expect(page.getByTestId("slots-booking-modal")).toBeVisible({ timeout: 10000 });
      await page.getByRole("button", { name: /отмена|закрыть/i }).first().click();
      await expect(page.getByTestId("slots-booking-modal")).toBeHidden({ timeout: 10000 });
      return;
    }

    if (await rescheduleBtn.count()) {
      await rescheduleBtn.click();
      await expect(page.getByTestId("slots-reschedule-modal")).toBeVisible({ timeout: 10000 });
      await page.getByRole("button", { name: /отмена|закрыть/i }).first().click();
      await expect(page.getByTestId("slots-reschedule-modal")).toBeHidden({ timeout: 10000 });
    }
  });

  test("messenger desktop keeps split layout visible", async ({ page }) => {
    await page.goto("/app/messenger");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    await expect(page.getByRole("heading", { name: "Мессенджер RecruitSmart" })).toBeVisible({ timeout: 10000 });
    await expect(page.locator(".messenger-sidebar")).toBeVisible({ timeout: 10000 });
    await expect(page.locator(".messenger-chat")).toBeVisible({ timeout: 10000 });
    await expect(page.locator(".background-scene")).toHaveCount(0);
  });

  test("candidate detail opens interview script modal", async ({ page }) => {
    await openFirstCandidateDetail(page);
    await expect(page.getByTestId("candidate-actions")).toBeVisible({ timeout: 10000 });

    await page.getByRole("button", { name: "Скрипт интервью" }).click();
    await expect(page.getByTestId("interview-script-modal")).toBeVisible({ timeout: 10000 });
  });
});

test.describe("ui cosmetics smoke (mobile 390)", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("dashboard has no horizontal overflow", async ({ page }) => {
    await page.goto("/app/dashboard");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    const expandedIncoming = page.getByTestId("incoming-filter-bar");
    if (await expandedIncoming.count()) {
      await expect(expandedIncoming).toBeVisible({ timeout: 10000 });
      await expectNoHorizontalOverflow(page);
      return;
    }

    const incomingSurface = page.getByTestId("dashboard-incoming-fullscreen");
    if (await incomingSurface.count()) {
      await expect(incomingSurface).toBeVisible({ timeout: 10000 });
    } else {
      await expect(page.getByText("Общая сводка")).toBeVisible({ timeout: 10000 });
    }
    await expectNoHorizontalOverflow(page);
  });

  test("incoming has no horizontal overflow", async ({ page }) => {
    await page.goto("/app/incoming");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);
    await expect(page.getByTestId("incoming-filter-bar")).toBeVisible({ timeout: 10000 });
    await expectNoHorizontalOverflow(page);
  });

  test("slots has no horizontal overflow", async ({ page }) => {
    await page.goto("/app/slots");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);
    await expect(page.getByTestId("slots-filter-bar")).toBeVisible({ timeout: 10000 });
    await expectNoHorizontalOverflow(page);
  });

  test("candidate detail main blocks are visible", async ({ page }) => {
    await openFirstCandidateDetail(page);
    await expect(page.getByTestId("candidate-actions")).toBeVisible({ timeout: 10000 });
    await expectNoHorizontalOverflow(page);
  });
});
