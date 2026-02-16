import { defineConfig, devices } from '@playwright/test';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const port = Number(process.env.PORT || 18000);
const host = process.env.HOST || '127.0.0.1';
const baseURL = `http://${host}:${port}`;
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '../..');
const pythonBin = path.join(repoRoot, '.venv', 'bin', 'python');
const e2eDataDir = path.join(repoRoot, '.tmp', 'e2e-data');
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
  workers: process.env.CI ? 2 : 1,
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
    command: `${pythonBin} scripts/run_migrations.py && ${pythonBin} -m uvicorn backend.apps.admin_ui.app:app --host ${host} --port ${port}`,
    cwd: repoRoot,
    url: `${baseURL}/health`,
    reuseExistingServer: false,
    stdout: 'pipe',
    stderr: 'pipe',
    timeout: 120 * 1000,
    env: {
      ENVIRONMENT: process.env.ENVIRONMENT || 'test',
      ADMIN_USER: process.env.ADMIN_USER || 'playwright_admin',
      ADMIN_PASSWORD: process.env.ADMIN_PASSWORD || 'playwright_admin_password',
      // E2E uses Playwright httpCredentials (Basic auth). Keep it enabled for the test server.
      ALLOW_LEGACY_BASIC: process.env.ALLOW_LEGACY_BASIC || '1',
      // Avoid brittle auth flows in E2E; keep prod-safe default (disabled) elsewhere.
      ALLOW_DEV_AUTOADMIN: process.env.ALLOW_DEV_AUTOADMIN || '1',
      SESSION_SECRET:
        process.env.SESSION_SECRET ||
        'playwright-secret-session-key-please-change-this-1234567890',
      AI_ENABLED: process.env.AI_ENABLED || '1',
      AI_PROVIDER: process.env.AI_PROVIDER || 'fake',
      E2E_SEED_AI: process.env.E2E_SEED_AI || '1',
      BOT_ENABLED: 'false',
      BOT_AUTOSTART: 'false',
      NOTIFICATION_BROKER: 'memory',
      PYTHONPATH: process.env.PYTHONPATH
        ? `${process.env.PYTHONPATH}:${repoRoot}`
        : repoRoot,
      DATABASE_URL:
        process.env.DATABASE_URL || `sqlite+aiosqlite:///${sqlitePath}`,
      DATA_DIR: process.env.DATA_DIR || e2eDataDir,
    },
  },
});
