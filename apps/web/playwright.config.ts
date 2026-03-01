import { defineConfig } from "@playwright/test";

const isCI = Boolean(process.env.CI);

/**
 * Playwright E2E test configuration.
 *
 * ## Running locally
 *
 * 1. Start Docker services with mock mode:
 *
 *      docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d
 *
 * 2. Run the tests (Playwright auto-starts a Next.js dev server on port 3001):
 *
 *      npm run test:e2e
 *
 * ## CI
 *
 * The GitHub Actions workflow starts both servers and sets PLAYWRIGHT_BASE_URL.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: isCI ? 2 : 0,
  forbidOnly: isCI,
  fullyParallel: true,
  use: {
    baseURL: isCI
      ? process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000"
      : "http://localhost:3001",
    trace: isCI ? "on-first-retry" : "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  reporter: isCI ? [["github"], ["html", { open: "never" }]] : "list",

  // Locally, start a Next.js dev server on port 3001 (avoids collision with
  // the Docker web container on 3000). The Docker API on port 8000 must already
  // be running with PATHFINDER_CHAT_PROVIDER=mock.
  ...(!isCI && {
    webServer: {
      command: "npm run dev -- -p 3001",
      port: 3001,
      timeout: 30_000,
      reuseExistingServer: true,
      env: {
        ...process.env,
        NEXT_PUBLIC_API_URL: "http://localhost:8000",
      },
    },
  }),
});
