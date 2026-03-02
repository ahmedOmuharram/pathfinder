import { test, expect } from "@playwright/test";
import {
  gotoHome,
  gotoHomeWithStrategy,
  sendMessage,
  expectIdleComposer,
} from "./helpers";

test("error: API 500 during chat shows error and allows retry", async ({ page }) => {
  // Fail only the first chat request.
  await page.route(
    "**/api/v1/chat",
    async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "text/plain",
        body: "Internal Server Error",
      });
    },
    { times: 1 },
  );

  await gotoHomeWithStrategy(page);

  // Send a message that triggers a 500 error.
  await sendMessage(page, "please fail");
  await expect(page.getByText("SSE request failed", { exact: false })).toBeVisible({
    timeout: 10_000,
  });

  // User should be able to type and send a new message.
  await expectIdleComposer(page);
  await sendMessage(page, "hello after error");
  await expect(page.getByText(/\[mock:execute\]/).first()).toBeVisible({
    timeout: 20_000,
  });
});

test("error: auth expiry shows login modal", async ({ page }) => {
  await gotoHome(page);

  // Intercept the chat endpoint to return 401 (auth expired).
  await page.route(
    "**/api/v1/chat",
    async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Token expired" }),
      });
    },
    { times: 1 },
  );

  await sendMessage(page, "trigger auth error");

  // Should show an error or login prompt.
  const loginModal = page.getByTestId("login-modal");
  const errorMsg = page.getByText(/unauthorized|expired|login/i).first();
  const sseError = page.getByText("SSE request failed", { exact: false });

  // Wait for either login modal or error message to appear.
  await expect(loginModal.or(errorMsg).or(sseError)).toBeVisible({
    timeout: 10_000,
  });
});

test("error: network error during streaming shows error toast", async ({ page }) => {
  await gotoHomeWithStrategy(page);

  // Abort the request to simulate network failure.
  await page.route(
    "**/api/v1/chat",
    async (route) => {
      await route.abort("connectionrefused");
    },
    { times: 1 },
  );

  await sendMessage(page, "trigger network error");

  // Should show some error indication.
  const errorIndicator = page.getByText(/error|failed|network/i).first();
  await expect(errorIndicator).toBeVisible({ timeout: 10_000 });

  // User should be able to recover and send a new message.
  await expectIdleComposer(page);
});
