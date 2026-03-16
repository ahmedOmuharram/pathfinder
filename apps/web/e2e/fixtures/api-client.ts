import type { APIRequestContext, BrowserContext } from "@playwright/test";
import { request } from "@playwright/test";

/**
 * Create an authenticated API client for postcondition verification.
 *
 * Copies cookies from the browser context so the API client shares
 * the same auth session. This client is for ASSERTING server-side
 * state after UI actions — never for setup.
 */
export async function createApiClient(
  context: BrowserContext,
  baseURL: string,
): Promise<APIRequestContext> {
  const cookies = await context.cookies();
  const authCookie = cookies.find((c) => c.name === "pathfinder-auth");

  return request.newContext({
    baseURL,
    extraHTTPHeaders: authCookie
      ? { Cookie: `pathfinder-auth=${authCookie.value}` }
      : {},
  });
}

export type ApiClient = APIRequestContext;

/**
 * Delete all gene sets for the current user via the API.
 *
 * Cleans gene sets across all VEuPathDB sites (default + site-specific)
 * to prevent cross-site pollution between tests.
 *
 * Uses `page.context().request` so cookies are shared with the browser.
 * Call from `beforeEach` in workbench/gene-set specs for test isolation.
 */
export async function clearAllGeneSets(
  context: BrowserContext,
  baseURL: string,
): Promise<void> {
  const req = context.request;
  const siteIds = [undefined, "plasmodb", "toxodb", "cryptodb", "fungidb", "tritrypdb"];
  await Promise.all(
    siteIds.map(async (siteId) => {
      const url = siteId
        ? `${baseURL}/api/v1/gene-sets?siteId=${siteId}`
        : `${baseURL}/api/v1/gene-sets`;
      const listResp = await req.get(url);
      if (!listResp.ok()) return;
      const geneSets = (await listResp.json()) as { id: string }[];
      await Promise.all(
        geneSets.map((gs) => req.delete(`${baseURL}/api/v1/gene-sets/${gs.id}`)),
      );
    }),
  );
}
