import { expect, type Page } from "@playwright/test";

/**
 * Authenticate the browser session for e2e tests.
 *
 * 1. Calls the mock-only `/api/v1/dev/login` endpoint to create a test user
 *    and obtain a valid `pathfinder-auth` token + cookie.
 * 2. Intercepts VEuPathDB auth-status requests so the frontend login gate
 *    sees `signedIn: true`.
 * 3. Intercepts VEuPathDB auth-refresh requests so the on-load refresh
 *    succeeds without a real VEuPathDB session.
 */
async function setupAuth(page: Page) {
  const apiBase = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";

  // 1. Obtain a valid auth token from the dev-only endpoint (with retry).
  let resp = await page.request.post(`${apiBase}/api/v1/dev/login`);
  if (!resp.ok()) {
    // Parallel workers can race on user creation — retry once.
    await page.waitForTimeout(500);
    resp = await page.request.post(`${apiBase}/api/v1/dev/login`);
  }
  expect(resp.ok()).toBeTruthy();
  const { authToken } = (await resp.json()) as { authToken: string };

  // 2. Store the token in localStorage so the Zustand store picks it up.
  await page.addInitScript((token: string) => {
    window.localStorage.setItem("pathfinder-auth-token", token);
  }, authToken);

  // 3. Mock VEuPathDB auth-status → signed in.
  await page.route("**/api/v1/veupathdb/auth/status*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        signedIn: true,
        name: "E2E User",
        email: "e2e@test.local",
      }),
    }),
  );

  // 4. Mock VEuPathDB auth-refresh → return the same token.
  await page.route("**/api/v1/veupathdb/auth/refresh", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, authToken }),
      headers: {
        "Set-Cookie": `pathfinder-auth=${authToken}; Path=/; HttpOnly; SameSite=Lax`,
      },
    }),
  );
}

/**
 * Navigate to the home page in plan mode (default — no strategy selected).
 */
export async function gotoHome(page: Page) {
  await setupAuth(page);
  await page.goto("/");
  await expect(page.getByTestId("message-composer")).toBeVisible();
}

/**
 * Navigate to the home page with a test strategy selected (execute mode).
 *
 * Creates a strategy via the API before navigation so it shows up in the
 * unified sidebar, then clicks it by its unique `data-conversation-id` to
 * enter execute mode.
 */
export async function gotoHomeWithStrategy(page: Page) {
  await setupAuth(page);

  const apiBase = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
  const uniqueName = `E2E Strategy ${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  const createResp = await page.request.post(`${apiBase}/api/v1/strategies`, {
    data: {
      name: uniqueName,
      siteId: "plasmodb",
      plan: {
        recordType: "gene",
        root: { searchName: "GenesByTaxon", parameters: {} },
      },
    },
  });
  expect(createResp.ok()).toBeTruthy();
  const { id: strategyId } = (await createResp.json()) as { id: string };

  await page.goto("/");
  await expect(page.getByTestId("message-composer")).toBeVisible();

  // Select the strategy by its unique conversation-id to avoid strict mode
  // violations when parallel tests create strategies with similar names.
  const item = page.locator(
    `[data-testid="conversation-item"][data-conversation-id="${strategyId}"]`,
  );
  await expect(item).toBeVisible({ timeout: 10_000 });
  await item.click();
}

export async function sendMessage(page: Page, message: string) {
  await page.getByTestId("message-input").fill(message);
  await page.getByTestId("send-button").click();
}

/**
 * Open the graph editor modal by clicking "Edit" in the CompactStrategyView.
 * Requires a strategy with steps to be rendered.
 */
export async function openGraphEditor(page: Page) {
  const editBtn = page.getByRole("button", { name: "Edit" });
  await expect(editBtn).toBeVisible({ timeout: 20_000 });
  await editBtn.click();
  // The modal has both an sr-only heading and a visible span with "Graph Editor".
  // Target the visible span specifically to avoid strict mode violation.
  await expect(page.locator("span").filter({ hasText: "Graph Editor" })).toBeVisible();
}

/**
 * Close the graph editor modal.
 */
export async function closeGraphEditor(page: Page) {
  const closeBtn = page.getByRole("button", { name: "Close" });
  await closeBtn.click();
  await expect(page.getByTestId("message-composer")).toBeVisible();
}

export async function expectIdleComposer(page: Page) {
  await expect(page.getByTestId("send-button")).toBeVisible();
}

export async function expectStreaming(page: Page) {
  await expect(page.getByTestId("stop-button")).toBeVisible();
}
