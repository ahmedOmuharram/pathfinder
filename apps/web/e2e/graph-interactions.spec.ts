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
 * Clamp a value to [min, max].
 */
function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

/**
 * Perform a single box-select drag around the given node bounding boxes,
 * clamped within the ReactFlow container.
 */
async function performBoxSelectDrag(
  page: Page,
  boxes: { x: number; y: number; width: number; height: number }[],
  containerBox: { x: number; y: number; width: number; height: number },
) {
  const PAD = 40;
  const INSET = 5;

  const minX = Math.min(...boxes.map((b) => b.x));
  const minY = Math.min(...boxes.map((b) => b.y));
  const maxX = Math.max(...boxes.map((b) => b.x + b.width));
  const maxY = Math.max(...boxes.map((b) => b.y + b.height));

  const left = clamp(
    minX - PAD,
    containerBox.x + INSET,
    containerBox.x + containerBox.width - INSET,
  );
  const top = clamp(
    minY - PAD,
    containerBox.y + INSET,
    containerBox.y + containerBox.height - INSET,
  );
  const right = clamp(
    maxX + PAD,
    containerBox.x + INSET,
    containerBox.x + containerBox.width - INSET,
  );
  const bottom = clamp(
    maxY + PAD,
    containerBox.y + INSET,
    containerBox.y + containerBox.height - INSET,
  );

  await page.mouse.move(left, top);
  await page.mouse.down();
  await page.mouse.move(right, bottom, { steps: 10 });
  await page.mouse.up();
}

/**
 * Select all visible nodes using box-select mode.
 *
 * Drags a selection rectangle across the full ReactFlow container to
 * select everything. Starts from the bottom-left corner (away from the
 * toolbar in the top-right) and ends at the top-right, sweeping the
 * entire canvas. Retries up to 3 times if ReactFlow doesn't register
 * the selection.
 */
async function boxSelectAllNodes(page: Page) {
  const boxSelectBtn = page.getByRole("button", { name: "Box select mode" });
  await boxSelectBtn.click();
  await expect(boxSelectBtn).toHaveAttribute("aria-pressed", "true", {
    timeout: 5_000,
  });

  const container = page.locator(".react-flow").first();
  const addSelectionBtn = page.getByRole("button", { name: "Add selection to chat" });

  for (let attempt = 0; attempt < 3; attempt++) {
    const cb = await container.boundingBox();
    expect(cb).toBeTruthy();
    if (!cb) return;

    // Drag from bottom-left to top-right of the ReactFlow container.
    // Starting from the bottom-left avoids the toolbar overlay (top-right)
    // and the controls panel (bottom-left small area, offset by 10px).
    const startX = cb.x + 10;
    const startY = cb.y + cb.height - 10;
    const endX = cb.x + cb.width - 10;
    const endY = cb.y + 10;

    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(endX, endY, { steps: 10 });
    await page.mouse.up();
    await page.waitForTimeout(300);

    const isSelected = await addSelectionBtn.isEnabled().catch(() => false);
    if (isSelected) return;

    await page.waitForTimeout(500);
  }
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
  await page.waitForTimeout(500);
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
  await page.waitForTimeout(500);
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

  // 7) Delete a node: click to select (opens StepEditor), close via Cancel
  //    (not Escape — Escape also deselects in ReactFlow), then Backspace.
  await page.getByRole("button", { name: "fit view" }).click();
  await page.waitForTimeout(500);

  const searchNode = page.getByTestId("rf-node-mock_search_1");
  await searchNode.click();

  // Close StepEditor via the Cancel button so the node stays selected.
  const cancelBtn = page.getByRole("button", { name: "Cancel" });
  await expect(cancelBtn).toBeVisible({ timeout: 5_000 });
  await cancelBtn.click();

  // Wait for the modal to fully close.
  await expect(cancelBtn).not.toBeVisible({ timeout: 5_000 });

  // Focus the ReactFlow canvas and delete the selected node.
  await page.locator(".react-flow").first().focus();
  await page.waitForTimeout(100);
  await page.keyboard.press("Backspace");
  await expect(page.getByTestId("rf-node-mock_search_1")).toHaveCount(0, {
    timeout: 10_000,
  });

  await expect(page.getByTestId("rf-handle-mock_transform_1-output")).toHaveClass(
    /opacity-0/,
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("rf-handle-mock_transform_1-primary")).toBeVisible();
});
