import { test, expect } from "@playwright/test";
import { gotoHome, switchToExecute } from "./helpers";

test("execute: switching site updates the selector", async ({ page }) => {
  await gotoHome(page);
  await switchToExecute(page);

  const select = page.getByTestId("site-select");
  await expect(select).toBeVisible();

  await select.selectOption("toxodb");
  await expect(select).toHaveValue("toxodb");
});
