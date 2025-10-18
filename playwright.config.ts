import { defineConfig, devices } from "@playwright/test";

const PORT = 8000;
export default defineConfig({
  testDir: "tests/e2e",
  timeout: 30_000,
  fullyParallel: false,
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    viewport: { width: 1280, height: 800 }
  },
  webServer: {
    command: "uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8000",
    port: PORT,
    reuseExistingServer: true,
    timeout: 60_000
  },
  reporter: [["html", { outputFolder: "playwright-report", open: "never" }]]
});
