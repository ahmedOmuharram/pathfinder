import { test, expect } from "@playwright/test";
import { gotoHome, switchToPlan, sendMessage } from "./helpers";

test("plan: send message and transition to executor", async ({ page }) => {
  await gotoHome(page);
  await switchToPlan(page);

  await sendMessage(page, "please build this in executor");

  // We should see a plan-mode response first.
  await expect(page.locator("text=[mock:plan]").first()).toBeVisible();

  // Then the UI should switch to executor mode (triggered by executor_build_request).
  await expect(page.getByTestId("mode-toggle-execute")).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  // And we should see the executor response begin.
  await expect(page.locator("text=[mock:execute]").first()).toBeVisible();
});
