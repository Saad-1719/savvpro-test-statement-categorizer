import { defineConfig, devices } from "@playwright/test";

// End-to-end tests: a real browser against the real backend and the Next.js dev server.
// Locally, set PLAYWRIGHT_CHANNEL=chrome to use an installed Chrome instead of downloading Chromium.
// E2E_BACKEND_CMD overrides how the backend is started (CI uses its own Python setup).
const backendCommand =
  process.env.E2E_BACKEND_CMD ?? "cd ../backend && .venv/bin/uvicorn app.main:app --port 8000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"], channel: process.env.PLAYWRIGHT_CHANNEL } },
  ],
  webServer: [
    { command: backendCommand, url: "http://localhost:8000/api/health", reuseExistingServer: !process.env.CI },
    { command: "npm run dev", url: "http://localhost:3000", reuseExistingServer: !process.env.CI, timeout: 120_000 },
  ],
});
