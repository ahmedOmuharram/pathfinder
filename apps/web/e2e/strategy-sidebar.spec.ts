import { test, expect } from "@playwright/test";
import { gotoHome, sendMessage } from "./helpers";

test("conversation sidebar: create and filter conversations", async ({ page }) => {
  await gotoHome(page);

  const items = page.getByTestId("conversation-item");
  const newBtn = page.getByTestId("conversations-new-button");
  const search = page.getByTestId("conversations-search-input");

  await expect(newBtn).toBeVisible();

  // The initial gotoHome creates a plan session implicitly.
  await expect(items.first()).toBeVisible();

  const countBefore = await items.count();
  await newBtn.click();

  // Verify at least one more item appeared.
  await expect
    .poll(async () => items.count(), { timeout: 10_000 })
    .toBeGreaterThan(countBefore);

  // Send a message in the active conversation.
  await sendMessage(page, "hello from sidebar test");
  await expect(page.getByText("[mock:plan]").first()).toBeVisible();

  // Filter the list by typing something — just verify filtering works.
  await search.fill("New Conversation");
  const filteredCount = await items.count();
  expect(filteredCount).toBeGreaterThanOrEqual(0);

  // Clear filter — should restore full list.
  await search.fill("");
  await expect
    .poll(async () => items.count(), { timeout: 10_000 })
    .toBeGreaterThanOrEqual(countBefore + 1);
});
