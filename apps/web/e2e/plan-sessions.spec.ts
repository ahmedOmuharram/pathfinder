import { test, expect } from "@playwright/test";
import { gotoHome, switchToPlan, sendMessage } from "./helpers";

test("plan sessions: create, rename, search, delete", async ({ page }) => {
  await gotoHome(page);
  await switchToPlan(page);

  // First message establishes an auth token in localStorage (from message_start payload),
  // enabling plan session APIs/UI.
  await sendMessage(page, "hello plan sessions");
  await expect(page.locator("text=[mock:plan]").first()).toBeVisible();

  const newPlan = page.getByTestId("plans-new-plan-button");
  await expect(newPlan).toBeVisible();

  const planItems = page.getByTestId("plans-plan-item");
  await expect(planItems.first()).toBeVisible();
  const initialCount = await planItems.count();

  await newPlan.click();
  await expect(planItems).toHaveCount(initialCount + 1);

  // Rename from the plan panel header.
  await page.getByTestId("plan-title-edit").click();
  await page.getByTestId("plan-title-input").fill("QA Plan Title");
  await page.getByTestId("plan-title-save").click();
  await expect(page.getByTestId("plan-title")).toContainText("QA Plan Title", {
    timeout: 20_000,
  });

  // Search in sidebar.
  await page.getByTestId("plans-search-input").fill("QA Plan Title");
  await expect(planItems).toHaveCount(1);
  await expect(planItems.first()).toContainText("QA Plan Title");

  // Delete the visible plan.
  page.once("dialog", (d) => d.accept());
  await planItems.first().getByTestId("plans-delete-plan-button").click();
  await expect(planItems).toHaveCount(0);
});
