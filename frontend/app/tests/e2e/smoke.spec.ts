import { test, expect } from '@playwright/test';

type SmokeRoute = {
  path: string;
  heading: string;
};

// SPA routes are now at /app/*
const routes: SmokeRoute[] = [
  { path: '/app/dashboard', heading: 'Dashboard' },
  { path: '/app/slots', heading: 'Слоты' },
  { path: '/app/candidates', heading: 'Кандидаты' },
  { path: '/app/recruiters', heading: 'Рекрутёры' },
  { path: '/app/cities', heading: 'Города' },
  { path: '/app/templates', heading: 'Шаблоны' },
  { path: '/app/questions', heading: 'Вопросы' },
];

for (const route of routes) {
  test(`renders ${route.path} without console errors`, async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto(route.path);
    await page.waitForLoadState('networkidle');

    // Wait for lazy-loaded content
    await page.waitForTimeout(500);

    const heading = page.getByRole('heading', { name: route.heading, exact: false });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });

    // Filter out known non-critical errors
    const criticalErrors = consoleErrors.filter(
      (msg) => !msg.includes('favicon') && !msg.includes('404')
    );
    expect(criticalErrors).toEqual([]);
  });
}

test('legacy routes redirect to SPA', async ({ page }) => {
  // Test that legacy routes redirect to SPA equivalents
  await page.goto('/');
  await page.waitForURL(/\/app\/(dashboard)?/);

  await page.goto('/slots');
  await page.waitForURL('/app/slots');

  await page.goto('/candidates');
  await page.waitForURL('/app/candidates');
});
