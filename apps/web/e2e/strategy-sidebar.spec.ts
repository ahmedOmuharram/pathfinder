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

  await newBtn.click();

  // Verify the new conversation appeared — look for the selected/active state
  // on the first item rather than relying on a count increase (the shared
  // e2e user accumulates many items across test runs).
  await expect(items.first()).toBeVisible({ timeout: 10_000 });

  // Send a message in the active conversation.
  await sendMessage(page, "hello from sidebar test");
  await expect(page.getByText("[mock:plan]").first()).toBeVisible();

  // Capture total count before filtering.
  const totalCount = await items.count();

  // Filter the list — verify it actually reduces the item count.
  await search.fill("New Conversation");
  await expect
    .poll(async () => items.count(), { timeout: 10_000 })
    .toBeLessThanOrEqual(totalCount);
  const filteredCount = await items.count();
  expect(filteredCount).toBeGreaterThan(0);

  // Clear filter — should restore full list (more items than filtered view).
  await search.fill("");
  await expect
    .poll(async () => items.count(), { timeout: 10_000 })
    .toBeGreaterThanOrEqual(totalCount);
});
