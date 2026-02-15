import { test, expect } from "@playwright/test";
import { gotoHome } from "./helpers";

test("switching site updates the selector", async ({ page }) => {
  await gotoHome(page);

  // The site-select dropdown lives inside the ConversationSidebar.
  const select = page.getByTestId("site-select");
  await expect(select).toBeVisible();

  await select.selectOption("toxodb");
  await expect(select).toHaveValue("toxodb");
});
