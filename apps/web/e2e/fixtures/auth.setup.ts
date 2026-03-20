import { test as setup, expect } from "@playwright/test";

const AUTH_STATE_PATH = "e2e/.auth/state.json";

setup("authenticate via dev-login", async ({ page }) => {
  const baseURL = process.env["PLAYWRIGHT_BASE_URL"] ?? "http://localhost:3000";

  // 1. Navigate first so the browser context is bound to the app origin.
  await page.goto(baseURL);

  // 2. Call dev-login via context.request — this shares cookies with the
  //    browser context. The Set-Cookie header from the API response
  //    automatically populates the browser's cookie jar.
  const resp = await page.context().request.post(`${baseURL}/api/v1/dev/login`);
  expect(resp.ok(), `dev-login failed: ${resp.status()}`).toBeTruthy();
  const body = (await resp.json()) as { authToken: string; userId: string };
  expect(body.authToken).toBeTruthy();

  // 3. Clean up stale data from previous test runs so we start fresh.
  const req = page.context().request;
  const strategiesResp = await req.get(`${baseURL}/api/v1/strategies`);
  if (strategiesResp.ok()) {
    const strategies = (await strategiesResp.json()) as { id: string }[];
    await Promise.all(
      strategies.map((s) => req.delete(`${baseURL}/api/v1/strategies/${s.id}`)),
    );
  }
  const geneSetsResp = await req.get(`${baseURL}/api/v1/gene-sets`);
  if (geneSetsResp.ok()) {
    const geneSets = (await geneSetsResp.json()) as { id: string }[];
    await Promise.all(
      geneSets.map((gs) => req.delete(`${baseURL}/api/v1/gene-sets/${gs.id}`)),
    );
  }

  // 4. Reload so the app picks up the cookie during its auth check.
  await page.reload();

  // 5. Wait for the app to finish loading — login modal should NOT appear.
  await expect(page.getByTestId("message-composer")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 10_000 });

  // 6. Save authenticated browser state (cookies + localStorage).
  await page.context().storageState({ path: AUTH_STATE_PATH });
});
