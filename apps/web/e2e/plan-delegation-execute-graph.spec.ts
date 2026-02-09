import { test, expect } from "@playwright/test";
import { gotoHome, switchToPlan, switchToGraphView, sendMessage } from "./helpers";

test("plan → delegation draft → build in executor → sub-kani activity → graph view", async ({
  page,
}) => {
  await gotoHome(page);
  await switchToPlan(page);

  // Trigger deterministic delegation draft from mock provider (plan mode).
  await sendMessage(page, "please create delegation draft");

  await expect(page.getByTestId("delegation-draft-details")).toBeVisible();
  await page.getByTestId("delegation-draft-details").locator("summary").click();
  await expect(
    page.getByText("Build a gene strategy using an ortholog transform and a combine."),
  ).toBeVisible();

  // Transition into executor mode via the UI button.
  await page.getByTestId("delegation-build-executor").click({ force: true });

  // Executor chat should mount and auto-send the queued message.
  await expect(page.getByTestId("mode-toggle-execute")).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  // Assert sub-kani activity is rendered in execute transcript.
  // It lives inside the assistant "Thought" details, which is collapsed by default.
  const thought = page.locator("summary").filter({ hasText: "Thought" }).first();
  await expect(thought).toBeVisible({ timeout: 20_000 });
  await thought.click();
  const thoughtDetails = thought.locator("..");
  const subKani = thoughtDetails
    .locator("summary")
    .filter({ hasText: "Sub-kani Activity" })
    .first();
  await expect(subKani).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("delegate:build-strategy").first()).toBeVisible({
    timeout: 20_000,
  });

  // Switch to graph view and assert the delegated graph exists.
  await switchToGraphView(page);
  await page.getByRole("button", { name: "Fit view" }).click();
  await expect(page.getByText("Delegated search step")).toBeVisible();
  await expect(page.getByText("Delegated transform step")).toBeVisible();
  await expect(page.getByText("Delegated combine step")).toBeVisible();
});
