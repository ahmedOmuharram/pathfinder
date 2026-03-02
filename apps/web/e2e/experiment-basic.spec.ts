import { test, expect } from "@playwright/test";
import { gotoExperiments } from "./experiment-helpers";

test("experiment: navigate to experiments page", async ({ page }) => {
  await gotoExperiments(page);

  // The experiments page should render with a new experiment button.
  await expect(
    page.getByRole("button", { name: /new experiment/i }).first(),
  ).toBeVisible({ timeout: 10_000 });
});

test("experiment: new experiment wizard shows mode selection", async ({ page }) => {
  await gotoExperiments(page);

  await page
    .getByRole("button", { name: /new experiment/i })
    .first()
    .click();

  // Mode selection should be visible.
  await expect(page.getByTestId("mode-single")).toBeVisible({ timeout: 5_000 });
  await expect(page.getByTestId("mode-multistep")).toBeVisible();
});

test("experiment: site selector is available", async ({ page }) => {
  await gotoExperiments(page);

  // The site selector should be visible on the experiments page.
  const siteSelect = page.getByTestId("site-select");
  await expect(siteSelect).toBeVisible({ timeout: 10_000 });

  // Should default to a valid site.
  const value = await siteSelect.inputValue();
  expect(value).toBeTruthy();
});
