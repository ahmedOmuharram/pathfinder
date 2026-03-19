import { defineConfig, devices } from "@playwright/test";

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
 * 2. Run the tests:
 *
 *      yarn test:e2e
 *
 * ## CI
 *
 * The GitHub Actions workflow starts both servers and sets PLAYWRIGHT_BASE_URL.
 *
 * ## Worker isolation
 *
 * Each Playwright worker authenticates as a unique user via
 * `/dev/login?user_id=worker-{N}`. This means parallel workers never
 * share gene sets, strategies, or conversations — `clearAllGeneSets`
 * only affects the calling worker's user.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: isCI ? 120_000 : 60_000,
  expect: { timeout: 15_000 },
  retries: isCI ? 2 : 3,
  forbidOnly: isCI,
  fullyParallel: true,
  workers: 2,

  reporter: isCI
    ? [["github"], ["html", { open: "never" }]]
    : [["list"], ["html", { open: "on-failure" }]],

  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
    trace: isCI ? "on-first-retry" : "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },

  projects: [
    {
      name: "feature",
      testDir: "./e2e/feature",
    },
    {
      name: "cross-feature",
      testDir: "./e2e/cross-feature",
      timeout: 120_000,
      // All cross-feature tests run enrichment against live VEuPathDB WDK
      // APIs.  WDK rate-limits concurrent analysis requests, so serialize
      // tests within this project to avoid parallel enrichment calls.
      fullyParallel: false,
    },
    {
      name: "journey",
      testDir: "./e2e/journey",
      timeout: 180_000,
      // Journey tests run enrichment against live VEuPathDB WDK APIs.
      // WDK rate-limits concurrent analysis requests, so serialize these.
      fullyParallel: false,
    },
  ],

  // Both local and CI: the Docker web container on port 3000 serves the
  // production build (no HMR).  The Docker API on port 8000 must be running
  // with PATHFINDER_CHAT_PROVIDER=mock.
  //
  // Start services:  docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build api web
});
