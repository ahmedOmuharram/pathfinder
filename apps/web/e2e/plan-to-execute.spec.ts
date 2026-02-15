import { test, expect } from "@playwright/test";
import { gotoHome, sendMessage } from "./helpers";

test("plan: send message and receive plan-mode response", async ({ page }) => {
  await gotoHome(page);

  await sendMessage(page, "please help me plan a strategy");

  // In plan mode, the mock provider responds with a [mock:plan] prefix.
  await expect(page.locator("text=[mock:plan]").first()).toBeVisible({
    timeout: 20_000,
  });

  // Verify our user message is visible in the transcript.
  await expect(
    page.getByText("please help me plan a strategy", { exact: true }).first(),
  ).toBeVisible();
});
