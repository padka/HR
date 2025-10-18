import { test, expect } from '@playwright/test';

type SmokeRoute = {
  path: string;
  heading: string;
};

const routes: SmokeRoute[] = [
  { path: '/', heading: 'Контур управления рекрутингом' },
  { path: '/slots', heading: 'Слоты' },
  { path: '/candidates', heading: 'Кандидаты' },
  { path: '/recruiters', heading: 'Рекрутёры' },
  { path: '/templates', heading: 'Шаблоны сообщений' },
];

for (const route of routes) {
  test(`renders ${route.path} without JSON console errors`, async ({ page }) => {
    const consoleMessages: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleMessages.push(msg.text());
      }
    });

    await page.goto(route.path);
    await page.waitForLoadState('networkidle');

    const heading = page.getByRole('heading', { name: route.heading, exact: false });
    await expect(heading.first()).toBeVisible();

    expect(consoleMessages).toEqual([]);
  });
}
