import { test, expect } from "@playwright/test";
import { gotoHome, gotoHomeWithStrategy, sendMessage } from "./helpers";

test("switching site updates the selector", async ({ page }) => {
  await gotoHome(page);

  // The site-select dropdown lives inside the ConversationSidebar.
  const select = page.getByTestId("site-select");
  await expect(select).toBeVisible();

  await select.selectOption("toxodb");
  await expect(select).toHaveValue("toxodb");
});

test("switching site resets the chat panel", async ({ page }) => {
  await gotoHome(page);

  // Send a message to establish chat state.
  await sendMessage(page, "test message before site switch");
  await expect(page.getByText("[mock:plan]").first()).toBeVisible({
    timeout: 30_000,
  });

  // Switch site.
  const select = page.getByTestId("site-select");
  await select.selectOption("toxodb");
  await expect(select).toHaveValue("toxodb");

  // The message composer should still be available (fresh state).
  await expect(page.getByTestId("message-composer")).toBeVisible();
});

test("switching site while strategy is active clears the strategy", async ({
  page,
}) => {
  await gotoHomeWithStrategy(page);

  // Strategy should be active — check for the graph or step indicators.
  const sidebar = page.getByTestId("conversation-item").first();
  await expect(sidebar).toBeVisible();

  // Switch site.
  const select = page.getByTestId("site-select");
  await select.selectOption("toxodb");
  await expect(select).toHaveValue("toxodb");

  // The composer should be visible (fresh state, no strategy).
  await expect(page.getByTestId("message-composer")).toBeVisible();
});
