import { defineConfig, devices } from "@playwright/test";

const isCI = Boolean(process.env["CI"]);

/**
 * Playwright E2E test configuration.
 *
 * ## Running locally
 *
 * 1. Start Docker services with the explicit development overlays:
 *
 *      docker compose --env-file .env.test \
 *        -f docker-compose.yml \
 *        -f docker-compose.dev.yml \
 *        -f docker-compose.e2e.yml \
 *        up -d --build api web
 *
 * 2. Export the registered VEuPathDB token and run the tests:
 *
 *      export WDK_TEST_TOKEN=...   # from .env.dev; never printed or committed
 *      yarn test:e2e
 *
 * ## CI
 *
 * The GitHub Actions workflow starts both servers and sets PLAYWRIGHT_BASE_URL
 * and WDK_TEST_TOKEN.
 *
 * ## Authentication
 *
 * VEuPathDB refuses guest service calls, so every worker acts as the registered
 * account: `e2e/fixtures/test.ts` puts `WDK_TEST_TOKEN` in the `Authorization`
 * cookie of the per-worker storage state (`e2e/.auth/worker-{N}.json`), which is
 * the token the API forwards to WDK. PathFinder identity stays per worker via
 * `/dev/login?user_id=worker-{N}`, so parallel workers never share gene sets,
 * strategies, or conversations: `clearAllGeneSets` only affects the calling
 * worker's user. The postcondition client in `e2e/fixtures/api-client.ts` copies
 * the whole browser cookie jar, so it carries both cookies too.
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
    baseURL: process.env["PLAYWRIGHT_BASE_URL"] ?? "http://localhost:3000",
    trace: isCI ? "on-first-retry" : "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },

  projects: [
    {
      name: "feature",
      testDir: "./e2e/feature",
      timeout: 120_000,
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
  // production build (no HMR). The Docker API on port 8000 must be running
  // with PATHFINDER_CHAT_PROVIDER=mock via the dedicated test overlay.
  //
  // Start services: docker compose --env-file .env.test -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.e2e.yml up -d --build api web
});
