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
  const baseURL =
    page.context().browser()?.contexts()[0]?.pages()[0]?.url() ??
    "http://localhost:3000";
  const apiBase = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";

  // 1. Obtain a valid auth token from the dev-only endpoint.
  const resp = await page.request.post(`${apiBase}/api/v1/dev/login`);
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

export async function gotoHome(page: Page) {
  await setupAuth(page);
  await page.goto("/");
  await expect(page.getByTestId("message-composer")).toBeVisible();
}

export async function switchToPlan(page: Page) {
  await page.getByTestId("mode-toggle-plan").click();
  await expect(page.getByTestId("mode-toggle-plan")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
}

export async function switchToExecute(page: Page) {
  await page.getByTestId("mode-toggle-execute").click();
  await expect(page.getByTestId("mode-toggle-execute")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
}

export async function sendMessage(page: Page, message: string) {
  await page.getByTestId("message-input").fill(message);
  await page.getByTestId("send-button").click();
}

export async function switchToGraphView(page: Page) {
  const chatPreview = page.getByRole("button", { name: /chat preview/i }).first();
  if (await chatPreview.isVisible()) return;

  // The preview widget is a div with role=button, labeled "Graph preview" when chat is active.
  const graphPreview = page.getByRole("button", { name: /graph preview/i }).first();
  await expect(graphPreview).toBeVisible();
  await graphPreview.click();
  await expect(chatPreview).toBeVisible({ timeout: 20_000 });
}

export async function switchToChatView(page: Page) {
  const composer = page.getByTestId("message-composer");
  const graphPreview = page.getByRole("button", { name: /graph preview/i }).first();
  if (await graphPreview.isVisible()) return;
  const chatPreview = page.getByRole("button", { name: /chat preview/i }).first();
  await expect(chatPreview).toBeVisible();
  await chatPreview.click();
  await expect(graphPreview).toBeVisible({ timeout: 20_000 });
  await expect(composer).toBeVisible();
}

export async function expectIdleComposer(page: Page) {
  await expect(page.getByTestId("send-button")).toBeVisible();
}

export async function expectStreaming(page: Page) {
  await expect(page.getByTestId("stop-button")).toBeVisible();
}
