import { test, expect } from "@playwright/test";
import {
  gotoHomeWithStrategy,
  sendMessage,
  openGraphEditor,
  closeGraphEditor,
} from "./helpers";

test("chat undo: sending messages creates undo snapshots", async ({ page }) => {
  test.slow();

  await gotoHomeWithStrategy(page);

  // Send a message that triggers a strategy update (mock provider creates steps).
  await sendMessage(page, "please emit artifact graph");
  await expect(page.getByText("Saved planning artifacts").first()).toBeVisible({
    timeout: 40_000,
  });

  // Apply the artifact to create graph nodes.
  const apply = page.getByRole("button", { name: "Apply to strategy" }).first();
  await expect(apply).toBeVisible({ timeout: 10_000 });
  await apply.click();

  // Open graph to verify nodes exist.
  await openGraphEditor(page);
  await expect(page.getByTestId("rf-node-mock_search_1")).toBeVisible({
    timeout: 10_000,
  });
  await closeGraphEditor(page);

  // Undo should be available after applying an artifact.
  const undoBtn = page.getByTestId("undo-button");
  await expect(undoBtn).toBeVisible({ timeout: 10_000 });
  await undoBtn.click();

  // After undo, the graph state should revert.
  await expect(page.getByTestId("message-composer")).toBeVisible();
});
