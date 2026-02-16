import { test, expect } from "@playwright/test";
import { gotoHome, sendMessage } from "./helpers";

test("plan sessions: create, rename, search, delete", async ({ page }) => {
  await gotoHome(page);

  // Use a unique name per test run to avoid cross-contamination from the
  // shared e2e user's accumulated data across repeated test runs.
  const uniqueTitle = `QA Plan ${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

  // Send a message to verify streaming works (default mode is plan).
  await sendMessage(page, "hello plan sessions");
  await expect(page.locator("text=[mock:plan]").first()).toBeVisible({
    timeout: 30_000,
  });

  const newBtn = page.getByTestId("conversations-new-button");
  await expect(newBtn).toBeVisible();

  const items = page.getByTestId("conversation-item");
  await expect(items.first()).toBeVisible();

  await newBtn.click();

  // Verify the new conversation appeared — wait for the first item to be
  // visible rather than relying on a count increase (the shared e2e user
  // accumulates many items across repeated test runs).
  await expect(items.first()).toBeVisible({ timeout: 10_000 });

  // Rename via the dropdown menu on the newest item (first in the list).
  const firstItem = items.first();
  await firstItem
    .getByRole("button", { name: "Conversation actions" })
    .click({ force: true });
  await page.getByRole("menuitem", { name: "Rename" }).click();

  const renameInput = page.getByTestId("conversation-rename-input");
  await expect(renameInput).toBeVisible();
  await renameInput.fill(uniqueTitle);
  await renameInput.press("Enter");

  // Verify the rename took effect. Don't rely on the item staying in the
  // first position — other parallel tests may create conversations that
  // push it down. Instead, check that an item with the unique title exists.
  await expect(items.filter({ hasText: uniqueTitle }).first()).toBeVisible({
    timeout: 20_000,
  });

  // Search in sidebar — should find exactly the renamed item.
  const search = page.getByTestId("conversations-search-input");
  await search.fill(uniqueTitle);
  const filtered = page.getByTestId("conversation-item");
  await expect(filtered.first()).toContainText(uniqueTitle);

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
  await expect(filtered.filter({ hasText: uniqueTitle })).toHaveCount(0, {
    timeout: 10_000,
  });
});
