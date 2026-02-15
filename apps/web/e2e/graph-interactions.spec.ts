import { test, expect, type Page } from "@playwright/test";
import {
  gotoHomeWithStrategy,
  sendMessage,
  openGraphEditor,
  closeGraphEditor,
} from "./helpers";

async function dragTestIdTo(page: Page, sourceTestId: string, targetTestId: string) {
  const source = page.getByTestId(sourceTestId);
  const target = page.getByTestId(targetTestId);
  await expect(source).toBeVisible();
  await expect(target).toBeVisible();
  const sb = await source.boundingBox();
  const tb = await target.boundingBox();
  expect(sb).toBeTruthy();
  expect(tb).toBeTruthy();
  if (!sb || !tb) return;
  await page.mouse.move(sb.x + sb.width / 2, sb.y + sb.height / 2);
  await page.mouse.down();
  await page.mouse.move(tb.x + tb.width / 2, tb.y + tb.height / 2);
  await page.mouse.up();
}

/**
 * Select all visible nodes using box-select mode.
 *
 * Switches to "Box select" mode, then drags a selection rectangle
 * around both nodes. This avoids triggering `onNodeClick` (and thus
 * the StepEditor modal), which makes it far more reliable than
 * individual click-based selection.
 */
async function boxSelectAllNodes(page: Page) {
  // Ensure we're in Box select mode.
  const boxSelectBtn = page.getByRole("button", { name: "Box select mode" });
  await boxSelectBtn.click();
  await page.waitForTimeout(200);

  // Get bounding boxes of both nodes to compute a rectangle that encloses them.
  const n1 = page.getByTestId("rf-node-mock_search_1");
  const n2 = page.getByTestId("rf-node-mock_transform_1");
  const b1 = await n1.boundingBox();
  const b2 = await n2.boundingBox();
  expect(b1).toBeTruthy();
  expect(b2).toBeTruthy();
  if (!b1 || !b2) return;

  // Compute a box that encloses both nodes with some padding.
  const left = Math.min(b1.x, b2.x) - 20;
  const top = Math.min(b1.y, b2.y) - 20;
  const right = Math.max(b1.x + b1.width, b2.x + b2.width) + 20;
  const bottom = Math.max(b1.y + b1.height, b2.y + b2.height) + 20;

  // Drag from top-left to bottom-right to select all nodes.
  await page.mouse.move(left, top);
  await page.mouse.down();
  await page.mouse.move(right, bottom, { steps: 5 });
  await page.mouse.up();
  await page.waitForTimeout(300);
}

test("graph: add-to-chat, edge delete, combine, undo, reconnect, node delete", async ({
  page,
}) => {
  await gotoHomeWithStrategy(page);

  // Trigger mock provider to emit a multi-step artifact (see API mock stream).
  await sendMessage(page, "please emit artifact graph");
  await expect(page.getByText("Saved planning artifacts").first()).toBeVisible({
    timeout: 40_000,
  });
  const apply = page.getByRole("button", { name: "Apply to strategy" }).first();
  await expect(apply).toBeVisible({ timeout: 40_000 });
  await apply.click();

  // Open the graph editor modal.
  await openGraphEditor(page);
  await page.getByRole("button", { name: "fit view" }).click();

  // Sanity: graph has our deterministic nodes.
  await expect(page.getByTestId("rf-node-mock_search_1")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByTestId("rf-node-mock_transform_1")).toBeVisible({
    timeout: 20_000,
  });

  // 1) Add a single node to chat via the "Add to chat" button.
  await page.getByTestId("rf-add-to-chat-mock_transform_1").click();
  await closeGraphEditor(page);
  await expect(page.getByText("Mock transform step").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove" })).toBeVisible();

  // Back to graph for interaction tests.
  await openGraphEditor(page);

  // 2) Multi-select via box-select and add selection to chat.
  await page.getByRole("button", { name: "fit view" }).click();
  await boxSelectAllNodes(page);

  const addSelection = page.getByRole("button", {
    name: "Add selection to chat",
  });
  await expect(addSelection).toBeEnabled({ timeout: 10_000 });
  await addSelection.click();

  await closeGraphEditor(page);
  await expect(page.getByText("Mock search step").first()).toBeVisible();
  await expect(page.getByText("Mock transform step").first()).toBeVisible();

  // 3) Delete the connecting edge.
  await openGraphEditor(page);
  await page.getByRole("button", { name: "fit view" }).click();

  const edgeMenu = page.getByRole("menu", { name: "Edge actions" });
  const edgeInteraction = page.locator(".react-flow__edge-interaction").first();
  await expect(edgeInteraction).toBeAttached({ timeout: 10_000 });
  await edgeInteraction.dispatchEvent("click");
  if (!(await edgeMenu.isVisible().catch(() => false))) {
    const edgePath = page.locator(".react-flow__edge").first();
    await edgePath.dispatchEvent("click");
  }
  await expect(edgeMenu).toBeVisible({ timeout: 10_000 });
  await page.getByRole("menuitem", { name: "Delete edge" }).click();

  // After edge delete, both nodes are roots → output handles visible.
  await expect(page.getByTestId("rf-handle-mock_search_1-output")).toBeVisible();
  await expect(page.getByTestId("rf-handle-mock_transform_1-output")).toBeVisible();
  await expect(page.getByTestId("rf-handle-mock_transform_1-primary")).toBeVisible();

  // 4) Combine the two disconnected roots via box-select + toolbar.
  await page.getByRole("button", { name: "fit view" }).click();
  await page.waitForTimeout(300);
  await boxSelectAllNodes(page);

  const combineBtn = page.getByRole("button", {
    name: "Combine selected steps",
  });
  await expect(combineBtn).toBeEnabled({ timeout: 10_000 });
  await combineBtn.click();
  await expect(page.getByText("Create combine step").first()).toBeVisible();
  await page.getByRole("button", { name: "UNION" }).click();
  await expect(page.getByText("UNION combine").first()).toBeVisible();

  // 5) Undo combine → back to two roots.
  await page.keyboard.press(process.platform === "darwin" ? "Meta+z" : "Control+z");
  await expect(page.getByText("UNION combine")).toHaveCount(0, {
    timeout: 10_000,
  });
  await expect(page.getByTestId("rf-handle-mock_search_1-output")).toBeVisible();
  await expect(page.getByTestId("rf-handle-mock_transform_1-output")).toBeVisible();

  // 6) Reconnect by dragging output → primary input.
  await dragTestIdTo(
    page,
    "rf-handle-mock_search_1-output",
    "rf-handle-mock_transform_1-primary",
  );
  await expect(page.getByTestId("rf-handle-mock_search_1-output")).toHaveClass(
    /opacity-0/,
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("rf-handle-mock_transform_1-output")).toHaveClass(
    /opacity-0/,
    { timeout: 10_000 },
  );

  // 7) Delete a node: select it via box-select, then press Backspace.
  //    Box-select ensures the ReactFlow canvas retains focus (no StepEditor popup).
  await page.getByRole("button", { name: "fit view" }).click();
  await page.waitForTimeout(300);

  const searchNode = page.getByTestId("rf-node-mock_search_1");
  const searchBox = await searchNode.boundingBox();
  expect(searchBox).toBeTruthy();
  if (searchBox) {
    // Ensure we're in Box select mode.
    await page.getByRole("button", { name: "Box select mode" }).click();
    await page.waitForTimeout(200);

    // Box-select just the search node.
    await page.mouse.move(searchBox.x - 10, searchBox.y - 10);
    await page.mouse.down();
    await page.mouse.move(
      searchBox.x + searchBox.width + 10,
      searchBox.y + searchBox.height + 10,
      { steps: 5 },
    );
    await page.mouse.up();
    await page.waitForTimeout(300);

    // Now delete via keyboard (canvas has focus from box-select).
    await page.keyboard.press("Backspace");
  }
  await expect(page.getByTestId("rf-node-mock_search_1")).toHaveCount(0, {
    timeout: 10_000,
  });

  await expect(page.getByTestId("rf-handle-mock_transform_1-output")).toHaveClass(
    /opacity-0/,
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("rf-handle-mock_transform_1-primary")).toBeVisible();
});
