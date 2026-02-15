import { test, expect } from "@playwright/test";
import { gotoHome, sendMessage } from "./helpers";

test("plan sessions: create, rename, search, delete", async ({ page }) => {
  await gotoHome(page);

  // Send a message to verify streaming works (default mode is plan).
  await sendMessage(page, "hello plan sessions");
  await expect(page.locator("text=[mock:plan]").first()).toBeVisible();

  const newBtn = page.getByTestId("conversations-new-button");
  await expect(newBtn).toBeVisible();

  // Capture item count before creating a new conversation.
  const items = page.getByTestId("conversation-item");
  await expect(items.first()).toBeVisible();
  const countBefore = await items.count();

  await newBtn.click();

  // Verify at least one more item appeared (other parallel tests may also create items).
  await expect
    .poll(async () => items.count(), { timeout: 10_000 })
    .toBeGreaterThan(countBefore);

  // Rename via the dropdown menu on the newest item (first in the list).
  const firstItem = items.first();
  await firstItem
    .getByRole("button", { name: "Conversation actions" })
    .click({ force: true });
  await page.getByRole("menuitem", { name: "Rename" }).click();

  const renameInput = page.getByTestId("conversation-rename-input");
  await expect(renameInput).toBeVisible();
  await renameInput.fill("QA Plan Title");
  await renameInput.press("Enter");

  // Verify the rename took effect.
  await expect(firstItem).toContainText("QA Plan Title", { timeout: 20_000 });

  // Search in sidebar — should find at least the renamed item.
  const search = page.getByTestId("conversations-search-input");
  await search.fill("QA Plan Title");
  const filtered = page.getByTestId("conversation-item");
  await expect(filtered.first()).toContainText("QA Plan Title");

  // Delete via dropdown → Delete → confirm modal.
  await filtered
    .first()
    .getByRole("button", { name: "Conversation actions" })
    .click({ force: true });
  await page.getByRole("menuitem", { name: "Delete" }).click();

  // Confirm in the delete modal.
  await expect(page.getByText("Delete conversation")).toBeVisible();
  await page.getByRole("button", { name: "Delete" }).last().click();

  // Verify the renamed item is gone from the filtered view.
  await expect(filtered.filter({ hasText: "QA Plan Title" })).toHaveCount(0, {
    timeout: 10_000,
  });
});
