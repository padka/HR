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
    const incomingCard = page.getByTestId("incoming-row").first();
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

    await expect(page.getByRole("complementary", { name: "Чаты кандидатов" })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("searchbox", { name: "Поиск по чатам" })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("button", { name: /папки/i })).toBeVisible({ timeout: 10000 });
    await expect(page.locator(".messenger-sidebar")).toBeVisible({ timeout: 10000 });
    await expect(page.locator(".messenger-chat")).toBeVisible({ timeout: 10000 });

    const composer = page.getByTestId("messenger-composer");
    if (!(await composer.isVisible().catch(() => false))) {
      const firstThread = page.locator('.messenger-thread-card[role="button"]').first();
      if (await firstThread.count()) {
        await expect(firstThread).toBeVisible({ timeout: 10000 });
        await firstThread.click();
      }
    }

    if (await composer.isVisible().catch(() => false)) {
      await expect(page.getByRole("button", { name: "Отправить сообщение" })).toBeVisible({ timeout: 10000 });
      const messages = page.getByTestId("messenger-messages");
      await expect(messages).toBeVisible({ timeout: 10000 });
      await messages.evaluate((node) => {
        const element = node as HTMLElement;
        element.scrollTop = 0;
      });
      await expect(page.getByTestId("messenger-composer")).toBeInViewport();
    } else {
      await expect(page.getByText("Выберите диалог слева").or(page.getByText("Ничего не найдено")).first()).toBeVisible({
        timeout: 10000,
      });
    }

    await expect(page.getByRole("button", { name: "Детали" })).toHaveCount(0);
    await expect(page.locator(".background-scene")).toHaveCount(0);
    await expectNoHorizontalOverflow(page);
  });

  test("candidate detail insights drawer stays notes-first", async ({ page }) => {
    await openFirstCandidateDetail(page);
    await expect(page.getByTestId("candidate-actions")).toBeVisible({ timeout: 10000 });

    await page.getByTestId("candidate-insights-trigger").click();
    const drawer = page.getByTestId("candidate-insights-drawer");
    await expect(drawer).toBeVisible({ timeout: 10000 });
    await expect(drawer.getByRole("heading", { name: "Заметки по кандидату", exact: true })).toBeVisible({ timeout: 10000 });
    await expect(drawer.getByTestId("candidate-quick-notes")).toBeVisible({ timeout: 10000 });
    await expect(drawer.getByText("HeadHunter")).toBeVisible({ timeout: 10000 });
    await expect(drawer.getByText("AI-помощник")).toHaveCount(0);
    await expect(drawer.getByText("Карточка кандидата")).toHaveCount(0);
  });

  test("candidate detail drawer stays scrollable and pipeline cards keep compact states", async ({ page }) => {
    await openFirstCandidateDetail(page);

    await page.getByTestId("candidate-insights-trigger").click();
    const drawer = page.getByTestId("candidate-insights-drawer");
    await expect(drawer).toBeVisible({ timeout: 10000 });

    const drawerBody = drawer.locator(".candidate-drawer__body");
    const drawerScroll = await drawerBody.evaluate((node) => {
      const element = node as HTMLElement;
      const overflowY = window.getComputedStyle(element).overflowY;
      return {
        overflowY,
        clientHeight: element.clientHeight,
        scrollHeight: element.scrollHeight,
      };
    });

    expect(["auto", "scroll"]).toContain(drawerScroll.overflowY);
    expect(drawerScroll.clientHeight).toBeGreaterThan(0);
    expect(drawerScroll.scrollHeight).toBeGreaterThanOrEqual(drawerScroll.clientHeight);
    await expect(page.getByText("Краткий операционный контекст для рекрутера.")).toHaveCount(0);
    await expect(page.getByText("Единая лента значимых событий по кандидату.")).toHaveCount(0);
    await expect(page.getByText("Локальные заметки рекрутера по кандидату.")).toHaveCount(0);
    await expect(drawer.getByText("HeadHunter")).toBeVisible();
    await expect(drawer.getByTestId("candidate-quick-notes")).toBeVisible();

    const pipeline = page.getByTestId("candidate-pipeline");
    await expect(pipeline.locator(".candidate-pipeline-stage")).toHaveCount(6);
    await expect(pipeline.locator(".candidate-pipeline-stage--current")).toBeVisible();
    await expect(pipeline.locator(".candidate-pipeline-stage--upcoming").first()).toBeVisible();
    await expect(pipeline.locator(".candidate-pipeline-stage__preview")).toHaveCount(0);
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

  test("messenger keeps two-step mobile flow without overflow", async ({ page }) => {
    await page.goto("/app/messenger");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    await expect(page.getByRole("complementary", { name: "Чаты кандидатов" })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("button", { name: /папки/i })).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: /папки/i }).click();
    await expect(page.getByTestId("messenger-folder-rail")).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: /закрыть меню папок/i }).click();

    const firstThread = page.locator('.messenger-thread-card[role="button"]').first();
    if (await firstThread.count()) {
      await expect(firstThread).toBeVisible({ timeout: 10000 });
      await firstThread.click();
      await expect(page.getByTestId("messenger-composer")).toBeVisible({ timeout: 10000 });
      await page.getByRole("button", { name: "Контекст" }).click();
      await expect(page.getByTestId("messenger-context-panel")).toBeVisible({ timeout: 10000 });
    }

    await expectNoHorizontalOverflow(page);
  });

  test("candidate detail main blocks are visible", async ({ page }) => {
    await openFirstCandidateDetail(page);
    await expect(page.getByTestId("candidate-actions")).toBeVisible({ timeout: 10000 });
    await expectNoHorizontalOverflow(page);
  });

  test("candidate detail drawer uses full-width sheet on mobile", async ({ page }) => {
    await openFirstCandidateDetail(page);
    await page.getByTestId("candidate-insights-trigger").click();

    const drawer = page.getByTestId("candidate-insights-drawer");
    await expect(drawer).toBeVisible({ timeout: 10000 });

    const box = await drawer.boundingBox();
    expect(box).not.toBeNull();
    expect(box?.width ?? 0).toBeGreaterThan(360);
    expect(box?.height ?? 0).toBeGreaterThan(700);

    const scrollState = await drawer.locator(".candidate-drawer__body").evaluate((node) => {
      const element = node as HTMLElement;
      return {
        overflowY: window.getComputedStyle(element).overflowY,
        clientHeight: element.clientHeight,
        scrollHeight: element.scrollHeight,
      };
    });

    expect(["auto", "scroll"]).toContain(scrollState.overflowY);
    expect(scrollState.clientHeight).toBeGreaterThan(0);
    expect(scrollState.scrollHeight).toBeGreaterThanOrEqual(scrollState.clientHeight);
    await expectNoHorizontalOverflow(page);
  });
});
