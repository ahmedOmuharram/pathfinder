import { expect } from "@playwright/test";

import { test } from "../fixtures/test";

/**
 * The e2e stack serves the production build, so neither development overlay
 * exists to take the pointer events of the controls under it.
 */
test.describe("Dev overlays", () => {
  test("no dev overlay paints over the app", async ({ page, chatPage }) => {
    await chatPage.goto();

    await expect(page.locator("nextjs-portal")).toHaveCount(0);
    await expect(page.locator("[data-nextjs-dev-overlay]")).toHaveCount(0);
    await expect(page.locator(".tsqd-parent-container")).toHaveCount(0);
  });

  test("the nav rail settings button takes the first click", async ({
    chatPage,
    settingsPage,
  }) => {
    await chatPage.goto();

    await settingsPage.open();
    await settingsPage.expectAllTabsVisible();
  });
});
