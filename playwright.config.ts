import { defineConfig, devices } from '@playwright/test';

const port = Number(process.env.PORT || 8000);
const host = process.env.HOST || '127.0.0.1';
const baseURL = `http://${host}:${port}`;

export default defineConfig({
  testDir: 'tests/e2e',
  timeout: 30 * 1000,
  expect: {
    timeout: 5 * 1000,
  },
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: [['list']],
  use: {
    baseURL,
    trace: 'on-first-retry',
    headless: true,
    httpCredentials: {
      username: process.env.ADMIN_USER || 'playwright_admin',
      password: process.env.ADMIN_PASSWORD || 'playwright_admin_password',
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: `uvicorn backend.apps.admin_ui.app:app --host 0.0.0.0 --port ${port}`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    stdout: 'pipe',
    stderr: 'pipe',
    timeout: 120 * 1000,
    env: {
      ADMIN_USER: process.env.ADMIN_USER || 'playwright_admin',
      ADMIN_PASSWORD: process.env.ADMIN_PASSWORD || 'playwright_admin_password',
      SESSION_SECRET_KEY:
        process.env.SESSION_SECRET_KEY ||
        'playwright-secret-session-key-please-change-this-1234567890',
      PYTHONPATH: process.env.PYTHONPATH ? `${process.env.PYTHONPATH}:.` : '.',
      DATABASE_URL: process.env.DATABASE_URL || 'sqlite+aiosqlite:///./data/playwright.db',
    },
  },
});
