import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration.
 *
 * - Mocked e2e tests (e2e/*.mocked.spec.ts) intercept the API via
 *   page.route() and return deterministic responses. They do NOT require a
 *   real backend, Neon, or the Qwen endpoint.
 * - Live e2e tests (e2e/*.live.spec.ts) are gated behind RUN_LIVE_TESTS=1 and
 *   require a running backend + frontend. They are skipped by default.
 *
 * The webServer starts the Vite dev server for the mocked tests.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
