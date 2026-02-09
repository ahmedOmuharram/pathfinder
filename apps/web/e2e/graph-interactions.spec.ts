import { test, expect, type Page } from "@playwright/test";
import { gotoHome, switchToExecute, sendMessage, switchToGraphView } from "./helpers";

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

test("graph: selection → add-to-chat, edge delete, combine, undo, reconnect, node delete", async ({
  page,
}) => {
  await gotoHome(page);
  await switchToExecute(page);

  // Trigger mock provider to emit a multi-step artifact (see API mock stream).
  await sendMessage(page, "please emit artifact graph");
  await expect(page.getByText("Saved planning artifacts")).toBeVisible({
    timeout: 40_000,
  });
  const apply = page.getByRole("button", { name: "Apply to strategy" }).first();
  await expect(apply).toBeVisible({ timeout: 40_000 });
  await apply.click();

  await switchToGraphView(page);
  await page.getByRole("button", { name: "Fit view" }).click();

  // Sanity: graph has our deterministic nodes.
  await expect(page.getByTestId("rf-node-mock_search_1")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByTestId("rf-node-mock_transform_1")).toBeVisible({
    timeout: 20_000,
  });

  // 1) Add a single node to chat via node button.
  await page.getByTestId("rf-add-to-chat-mock_transform_1").click();
  await expect(page.getByText("Mock transform step").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove" })).toBeVisible();

  // Back to graph for interaction tests.
  await switchToGraphView(page);

  // 2) Box select both nodes and add selection to chat via toolbar.
  await page.locator('button[title="Box select"]').click();

  const n1 = page.getByTestId("rf-node-mock_search_1");
  const n2 = page.getByTestId("rf-node-mock_transform_1");
  await expect(n1).toBeVisible();
  await expect(n2).toBeVisible();
  const b1 = await n1.boundingBox();
  const b2 = await n2.boundingBox();
  expect(b1).toBeTruthy();
  expect(b2).toBeTruthy();
  if (!b1 || !b2) return;

  const left = Math.min(b1.x, b2.x) - 20;
  const top = Math.min(b1.y, b2.y) - 20;
  const right = Math.max(b1.x + b1.width, b2.x + b2.width) + 20;
  const bottom = Math.max(b1.y + b1.height, b2.y + b2.height) + 20;

  await page.mouse.move(left, top);
  await page.mouse.down();
  await page.mouse.move(right, bottom);
  await page.mouse.up();

  const addSelection = page.locator('button[title="Add selection to chat"]');
  await expect(addSelection).toBeEnabled({ timeout: 10_000 });
  await addSelection.click();
  await expect(page.getByText("Mock search step").first()).toBeVisible();
  await expect(page.getByText("Mock transform step").first()).toBeVisible();

  // Back to graph to delete the edge.
  await switchToGraphView(page);

  // 3) Delete the connecting edge via edge menu.
  await page.getByRole("button", { name: "Fit view" }).click();
  const edgeMenu = page.getByRole("dialog", { name: "Edge actions" });

  // ReactFlow SVG edge paths live in a transformed coordinate space that can
  // confuse Playwright's viewport calculations, so we use dispatchEvent which
  // bypasses viewport/actionability checks entirely.
  const edgeInteraction = page.locator(".react-flow__edge-interaction").first();
  await expect(edgeInteraction).toBeAttached({ timeout: 10_000 });
  await edgeInteraction.dispatchEvent("click");
  if (!(await edgeMenu.isVisible().catch(() => false))) {
    // Retry on the visible edge path itself.
    const edgePath = page.locator(".react-flow__edge").first();
    await edgePath.dispatchEvent("click");
  }
  await expect(edgeMenu).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Delete edge" }).click();

  // After edge delete, both nodes are roots => output handles become visible.
  await expect(page.getByTestId("rf-handle-mock_search_1-output")).toBeVisible();
  await expect(page.getByTestId("rf-handle-mock_transform_1-output")).toBeVisible();
  await expect(page.getByTestId("rf-handle-mock_transform_1-primary")).toBeVisible();

  // 4) Combine the two roots via toolbar gesture (multi-step flow).
  // Fit the graph first so both disconnected roots are centered in the viewport.
  await page.getByRole("button", { name: "Fit view" }).click();
  await page.waitForTimeout(300);

  await page.locator('button[title="Box select"]').click();

  // Use actual node positions (not the container box) for a reliable selection
  // rectangle, matching the approach in step 2 that works.
  const ns1 = page.getByTestId("rf-node-mock_search_1");
  const ns2 = page.getByTestId("rf-node-mock_transform_1");
  await expect(ns1).toBeVisible();
  await expect(ns2).toBeVisible();
  const bs1 = await ns1.boundingBox();
  const bs2 = await ns2.boundingBox();
  expect(bs1).toBeTruthy();
  expect(bs2).toBeTruthy();
  if (!bs1 || !bs2) return;

  const selLeft = Math.min(bs1.x, bs2.x) - 20;
  const selTop = Math.min(bs1.y, bs2.y) - 20;
  const selRight = Math.max(bs1.x + bs1.width, bs2.x + bs2.width) + 20;
  const selBottom = Math.max(bs1.y + bs1.height, bs2.y + bs2.height) + 20;

  await page.mouse.move(selLeft, selTop);
  await page.mouse.down();
  await page.mouse.move(selRight, selBottom);
  await page.mouse.up();

  const combineBtn = page.locator('button[title="Combine selected steps"]');
  await expect(combineBtn).toBeEnabled({ timeout: 10_000 });
  await combineBtn.click();
  await expect(page.getByText("Create combine step")).toBeVisible();
  await page.getByRole("button", { name: "UNION" }).click();
  await expect(page.getByText("UNION combine")).toBeVisible();

  // 5) Undo combine and verify we return to two-roots state.
  await page.keyboard.press(process.platform === "darwin" ? "Meta+z" : "Control+z");
  await expect(page.getByText("UNION combine")).toHaveCount(0);
  await expect(page.getByTestId("rf-handle-mock_search_1-output")).toBeVisible();
  await expect(page.getByTestId("rf-handle-mock_transform_1-output")).toBeVisible();

  // 6) Reconnect by dragging output -> primary input.
  await dragTestIdTo(
    page,
    "rf-handle-mock_search_1-output",
    "rf-handle-mock_transform_1-primary",
  );
  // Reconnected graph has single root => output handles get opacity-0 styling.
  // Note: we check the CSS class rather than toBeHidden() because ReactFlow's
  // base styles can override computed opacity in the headless Playwright viewport.
  await expect(page.getByTestId("rf-handle-mock_search_1-output")).toHaveClass(
    /opacity-0/,
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("rf-handle-mock_transform_1-output")).toHaveClass(
    /opacity-0/,
    { timeout: 10_000 },
  );

  // 7) Delete a node (search) and verify it disappears and downstream detaches.
  await page.getByTestId("rf-node-mock_search_1").click();
  await page.keyboard.press("Backspace");
  await expect(page.getByTestId("rf-node-mock_search_1")).toHaveCount(0);

  // Remaining single root => output handle gets opacity-0 styling; primary slot should reopen.
  await expect(page.getByTestId("rf-handle-mock_transform_1-output")).toHaveClass(
    /opacity-0/,
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("rf-handle-mock_transform_1-primary")).toBeVisible();
});
