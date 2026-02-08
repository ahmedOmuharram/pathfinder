import { test, expect } from "@playwright/test";

test("execute mode: send message and see streamed response", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("mode-toggle-execute").click();

  await page.getByTestId("message-input").fill("hello from e2e");
  await page.getByTestId("send-button").click();

  await expect(page.getByText("[mock:execute]")).toBeVisible();
  await expect(page.getByText("hello from e2e")).toBeVisible();
});

test("execute mode: stop streaming", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("mode-toggle-execute").click();

  await page.getByTestId("message-input").fill("slow please");
  await page.getByTestId("send-button").click();

  // Stop should become available quickly while streaming.
  const stop = page.getByTestId("stop-button");
  await expect(stop).toBeVisible();
  await stop.click();

  // After stopping, we should return to an idle composer state.
  await expect(page.getByTestId("send-button")).toBeVisible();
});

test("plan mode: send message and transition to executor", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("mode-toggle-plan").click();

  await page.getByTestId("message-input").fill("please build this in executor");
  await page.getByTestId("send-button").click();

  // We should see a plan-mode response first.
  await expect(page.getByText("[mock:plan]")).toBeVisible();

  // Then the UI should switch to executor mode (triggered by executor_build_request).
  await expect(page.getByTestId("mode-toggle-execute")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});
