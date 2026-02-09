import { test, expect } from "@playwright/test";
import { gotoHome, switchToExecute, sendMessage } from "./helpers";

test("execute: strategy sidebar can create and filter strategies", async ({ page }) => {
  await gotoHome(page);
  await switchToExecute(page);

  const items = page.getByTestId("strategies-item");
  const newBtn = page.getByTestId("strategies-new-button");
  const search = page.getByTestId("strategies-search-input");

  await expect(newBtn).toBeVisible();

  await newBtn.click();
  await expect(items.first()).toBeVisible();

  // Create some chat state on the active strategy.
  await sendMessage(page, "hello from strategy sidebar");
  await expect(page.getByText("[mock:execute]").first()).toBeVisible();

  // Filter the list by the visible strategy name.
  await search.fill("Draft");
  await expect(items.first()).toBeVisible();
});
