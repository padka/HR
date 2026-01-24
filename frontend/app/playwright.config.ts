import { defineConfig, devices } from '@playwright/test';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const port = Number(process.env.PORT || 8000);
const host = process.env.HOST || '127.0.0.1';
const baseURL = `http://${host}:${port}`;
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '../..');
const pythonBin = path.join(repoRoot, '.venv', 'bin', 'python');
const sqlitePath = path.join(
  os.tmpdir(),
  `recruitsmart_e2e_${process.pid}_${Date.now()}.db`,
);

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
    command: `${pythonBin} scripts/run_migrations.py && ${pythonBin} -m uvicorn backend.apps.admin_ui.app:app --host 0.0.0.0 --port ${port}`,
    cwd: repoRoot,
    url: `${baseURL}/health`,
    reuseExistingServer: !process.env.CI,
    stdout: 'pipe',
    stderr: 'pipe',
    timeout: 120 * 1000,
    env: {
      ADMIN_USER: process.env.ADMIN_USER || 'playwright_admin',
      ADMIN_PASSWORD: process.env.ADMIN_PASSWORD || 'playwright_admin_password',
      SESSION_SECRET:
        process.env.SESSION_SECRET ||
        'playwright-secret-session-key-please-change-this-1234567890',
      BOT_ENABLED: 'false',
      BOT_AUTOSTART: 'false',
      NOTIFICATION_BROKER: 'memory',
      PYTHONPATH: process.env.PYTHONPATH
        ? `${process.env.PYTHONPATH}:${repoRoot}`
        : repoRoot,
      DATABASE_URL:
        process.env.DATABASE_URL || `sqlite+aiosqlite:///${sqlitePath}`,
    },
  },
});
