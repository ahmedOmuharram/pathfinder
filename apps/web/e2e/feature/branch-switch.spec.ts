import { test, expect } from "../fixtures/test";

const BASE_URL = process.env["PLAYWRIGHT_BASE_URL"] ?? "http://localhost:3000";

function sseFrame(obj: unknown): string {
  return `data: ${JSON.stringify(obj)}\n\n`;
}

function chatStreamHeaders(): Record<string, string> {
  return {
    "content-type": "text/event-stream",
    "cache-control": "no-cache",
    "x-vercel-ai-ui-message-stream": "v1",
  };
}

interface OpenStrategyResponse {
  strategyId?: string;
  id?: string;
}

async function openStrategy(
  context: import("@playwright/test").BrowserContext,
): Promise<string> {
  const resp = await context.request.post(`${BASE_URL}/api/v1/conversations/open`, {
    data: { siteId: "veupathdb" },
    headers: { "X-Requested-With": "XMLHttpRequest" },
  });
  if (!resp.ok()) {
    throw new Error(`openStrategy failed: ${resp.status()}`);
  }
  const body = (await resp.json()) as OpenStrategyResponse;
  const id = body.strategyId ?? body.id;
  if (id === undefined || id === "") {
    throw new Error("openStrategy returned no id");
  }
  return id;
}

const CP_ROOT = "cp-root-100";
const CP_AFTER_MSG1 = "cp-msg1-101";
const CP_AFTER_MSG2 = "cp-msg2-102";
const CP_FORKED = "cp-forked-103";
const CP_AFTER_BRANCH_MSG1 = "cp-branch-msg1-104";

function baseCheckpoints(threadId: string): Array<Record<string, unknown>> {
  return [
    {
      checkpointId: CP_ROOT,
      parentCheckpointId: null,
      threadId,
      source: "input",
      step: 0,
      node: null,
      createdAt: "2026-04-15T10:00:00Z",
      label: null,
      pinned: false,
    },
    {
      checkpointId: CP_AFTER_MSG1,
      parentCheckpointId: CP_ROOT,
      threadId,
      source: "loop",
      step: 1,
      node: "scoping",
      createdAt: "2026-04-15T10:01:00Z",
      label: null,
      pinned: false,
    },
    {
      checkpointId: CP_AFTER_MSG2,
      parentCheckpointId: CP_AFTER_MSG1,
      threadId,
      source: "loop",
      step: 2,
      node: "scoping",
      createdAt: "2026-04-15T10:02:00Z",
      label: null,
      pinned: false,
    },
  ];
}

function checkpointsAfterFork(threadId: string): Array<Record<string, unknown>> {
  return [
    ...baseCheckpoints(threadId),
    {
      checkpointId: CP_FORKED,
      parentCheckpointId: CP_AFTER_MSG1,
      threadId,
      source: "fork",
      step: 3,
      node: "scoping",
      createdAt: "2026-04-15T10:03:00Z",
      label: null,
      pinned: false,
    },
  ];
}

function checkpointsAfterBranchMsg(threadId: string): Array<Record<string, unknown>> {
  return [
    ...checkpointsAfterFork(threadId),
    {
      checkpointId: CP_AFTER_BRANCH_MSG1,
      parentCheckpointId: CP_FORKED,
      threadId,
      source: "loop",
      step: 4,
      node: "scoping",
      createdAt: "2026-04-15T10:04:00Z",
      label: null,
      pinned: false,
    },
  ];
}

function buildChatStream(messageId: string, text: string): string {
  return [
    sseFrame({
      type: "messages/partial",
      messageId,
      delta: text,
    }),
    sseFrame({
      type: "messages/complete",
      messageId,
      role: "ai",
      content: text,
    }),
    "data: [DONE]\n\n",
  ].join("");
}

test.describe("Branch Switch", () => {
  test.describe.configure({ mode: "serial" });

  test("switching back to original branch preserves prior messages", async ({
    page,
    context,
  }) => {
    const strategyId = await openStrategy(context);

    let chatCallCount = 0;
    let checkpointPhase: "base" | "forked" | "branch-msg" = "base";

    const chatResponses = [
      "[mock] first message reply",
      "[mock] second message reply",
      "[mock] branch message reply",
    ];

    await page.route("**/api/v1/chat", async (route) => {
      const responseText = chatResponses[chatCallCount] ?? "[mock] extra";
      chatCallCount++;
      await route.fulfill({
        status: 200,
        headers: chatStreamHeaders(),
        body: buildChatStream(`msg-${chatCallCount}`, responseText),
      });
    });

    await page.route(`**/api/v1/conversations/*/checkpoints`, async (route) => {
      let checkpoints: Array<Record<string, unknown>>;
      switch (checkpointPhase) {
        case "base":
          checkpoints = baseCheckpoints(strategyId);
          break;
        case "forked":
          checkpoints = checkpointsAfterFork(strategyId);
          break;
        case "branch-msg":
          checkpoints = checkpointsAfterBranchMsg(strategyId);
          break;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(checkpoints),
      });
    });

    await page.route("**/api/v1/conversations/*/fork", async (route) => {
      checkpointPhase = "forked";
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({ newCheckpointId: CP_FORKED }),
      });
    });

    await page.goto(`/conversation/${strategyId}`);
    const composer = page.getByPlaceholder("Ask about strategies", {
      exact: false,
    });
    await expect(composer).toBeVisible({ timeout: 30_000 });

    const sendButton = page.getByRole("button", { name: /Send/i });

    await composer.click();
    await composer.pressSequentially("first message", { delay: 15 });
    await expect(sendButton).toBeEnabled({ timeout: 15_000 });
    await composer.press("Enter");
    await expect(page.getByText("[mock] first message reply")).toBeVisible({
      timeout: 30_000,
    });

    await composer.click();
    await composer.pressSequentially("second message", { delay: 15 });
    await expect(sendButton).toBeEnabled({ timeout: 15_000 });
    await composer.press("Enter");
    await expect(page.getByText("[mock] second message reply")).toBeVisible({
      timeout: 30_000,
    });

    const branchesButton = page.getByRole("button", { name: "Branches" });
    await branchesButton.click();
    const branchTree = page.getByTestId("branch-tree");
    await expect(branchTree).toBeVisible({ timeout: 15_000 });

    const checkpointNodes = branchTree.locator("[data-branch-node]");
    // TODO(weak-strict-mode): cannot disambiguate from test alone — the
    // [data-branch-node] selector is not present in current `src/` so the
    // intended structure (which checkpoint is "first") cannot be inferred.
    await expect(checkpointNodes.first()).toBeVisible({ timeout: 15_000 });

    // TODO(weak-strict-mode): cannot disambiguate from test alone.
    await checkpointNodes.first().click();

    const forkButton = page.getByRole("button", {
      name: "Fork from this checkpoint",
    });
    await expect(forkButton).toBeVisible({ timeout: 15_000 });
    await forkButton.click();

    await expect(page).toHaveURL(/\?branch=/, { timeout: 15_000 });

    checkpointPhase = "branch-msg";

    await composer.click();
    await composer.pressSequentially("branch message", { delay: 15 });
    await expect(sendButton).toBeEnabled({ timeout: 15_000 });
    await composer.press("Enter");
    await expect(page.getByText("[mock] branch message reply")).toBeVisible({
      timeout: 30_000,
    });

    const treeNodes = branchTree.locator("[data-branch-node]");
    await expect(treeNodes).toHaveCount(5, { timeout: 15_000 });

    // TODO(weak-strict-mode): cannot disambiguate from test alone — the
    // branch-tree component lives outside src/ (mock-only fixture) so we
    // cannot select the intended checkpoint node by stable id.
    const originalLeaf = treeNodes.nth(2);
    await originalLeaf.click();

    await expect(page).toHaveURL(new RegExp(`\\?branch=${CP_AFTER_MSG2}`), {
      timeout: 15_000,
    });

    await expect(page.getByText("[mock] first message reply")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText("[mock] second message reply")).toBeVisible({
      timeout: 15_000,
    });
  });
});
