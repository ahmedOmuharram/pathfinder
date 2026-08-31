import { expect, request } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

/**
 * One request per route pattern the suite enters. The production server loads
 * a route's module graph and renders it cold on the first request, so the
 * first spec to reach one pays a cost that has nothing to do with what it
 * asserts. The cost is per pattern, not per parameter value, so one site and
 * one id cover every conversation and workbench route.
 */
const ID = "00000000-0000-0000-0000-000000000001";
const SITE = "plasmodb";

const ROUTES = [
  "/",
  "/conversation",
  "/workbench",
  `/workbench/${ID}`,
  `/${SITE}/conversation`,
  `/${SITE}/conversation/${ID}`,
  `/${SITE}/conversation/${ID}/strategy`,
  `/${SITE}/conversation/${ID}/strategy/step/${ID}`,
  `/${SITE}/conversation/${ID}/eda`,
  `/${SITE}/workbench`,
  `/${SITE}/workbench/${ID}`,
  `/${SITE}/saved`,
];

const COLD_RENDER_BUDGET_MS = 180_000;
const LISTEN_BUDGET_MS = 120_000;

/** Wait for the web container to accept connections. A restarted container
 *  resets the socket until its server binds the port. */
async function waitForServer(api: APIRequestContext): Promise<void> {
  await expect(async () => {
    const response = await api.get("/", { timeout: 30_000 });
    expect(response.status()).toBeLessThan(500);
  }).toPass({ timeout: LISTEN_BUDGET_MS, intervals: [1_000, 2_000, 5_000] });
}

export default async function warmRoutes(): Promise<void> {
  const baseURL = process.env["PLAYWRIGHT_BASE_URL"] ?? "http://localhost:3000";
  const api = await request.newContext({ baseURL });
  try {
    await waitForServer(api);
    for (const route of ROUTES) {
      await api.get(route, { timeout: COLD_RENDER_BUDGET_MS });
    }
  } finally {
    await api.dispose();
  }
}
