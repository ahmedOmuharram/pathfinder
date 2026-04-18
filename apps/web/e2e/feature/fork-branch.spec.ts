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
  const resp = await context.request.post(
    `${BASE_URL}/api/v1/conversations/open`,
    {
      data: { siteId: "veupathdb" },
      headers: { "X-Requested-With": "XMLHttpRequest" },
    },
  );
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

const CHECKPOINT_ROOT = "cp-root-001";
const CHECKPOINT_AFTER_MSG1 = "cp-after-msg1-002";
const CHECKPOINT_FORKED = "cp-forked-003";

function makeCheckpoints(
  threadId: string,
): Array<Record<string, unknown>> {
  return [
    {
      checkpointId: CHECKPOINT_ROOT,
      parentCheckpointId: null,
      threadId,
      source: "input",
      step: 0,
      node: null,
      createdAt: new Date().toISOString(),
      label: null,
      pinned: false,
    },
    {
      checkpointId: CHECKPOINT_AFTER_MSG1,
      parentCheckpointId: CHECKPOINT_ROOT,
      threadId,
      source: "loop",
      step: 1,
      node: "scoping",
      createdAt: new Date().toISOString(),
      label: null,
      pinned: false,
    },
  ];
}

function makeCheckpointsAfterFork(
  threadId: string,
): Array<Record<string, unknown>> {
  return [
    ...makeCheckpoints(threadId),
    {
      checkpointId: CHECKPOINT_FORKED,
      parentCheckpointId: CHECKPOINT_ROOT,
      threadId,
      source: "fork",
      step: 2,
      node: "scoping",
      createdAt: new Date().toISOString(),
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

test.describe("Fork Branch", () => {
  test.describe.configure({ mode: "serial" });

  test("user forks from a checkpoint and gets a branched response", async ({
    page,
    context,
  }) => {
    const strategyId = await openStrategy(context);

    let chatCallCount = 0;
    let checkpointCallCount = 0;

    await page.route("**/api/v1/chat", async (route) => {
      chatCallCount++;
      const body = buildChatStream(
        chatCallCount === 1
          ? "msg-assistant-1"
          : "msg-assistant-branch-1",
        chatCallCount === 1
          ? "[mock] initial response"
          : "[mock] branched response for liver-stage",
      );
      await route.fulfill({
        status: 200,
        headers: chatStreamHeaders(),
        body,
      });
    });

    await page.route(
      `**/api/v1/conversations/*/checkpoints`,
      async (route) => {
        checkpointCallCount++;
        const checkpoints =
          checkpointCallCount <= 1
            ? makeCheckpoints(strategyId)
            : makeCheckpointsAfterFork(strategyId);
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(checkpoints),
        });
      },
    );

    await page.route("**/api/v1/conversations/*/fork", async (route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({ newCheckpointId: CHECKPOINT_FORKED }),
      });
    });

    await page.goto(`/conversation/${strategyId}`);
    const composer = page.getByPlaceholder("Ask about strategies", {
      exact: false,
    });
    await expect(composer).toBeVisible({ timeout: 30_000 });

    await composer.click();
    await composer.pressSequentially("Analyze malaria transcriptome", {
      delay: 15,
    });
    const sendButton = page.getByRole("button", { name: /Send/i });
    await expect(sendButton).toBeEnabled({ timeout: 15_000 });
    await composer.press("Enter");

    await expect(page.getByText("[mock] initial response")).toBeVisible({
      timeout: 30_000,
    });

    const branchesButton = page.getByRole("button", { name: "Branches" });
    await expect(branchesButton).toBeVisible({ timeout: 15_000 });
    await branchesButton.click();

    const branchTree = page.getByTestId("branch-tree");
    await expect(branchTree).toBeVisible({ timeout: 15_000 });

    const checkpointNodes = branchTree.locator("[data-branch-node]");
    await expect(checkpointNodes).toHaveCount(2, { timeout: 15_000 });
    await checkpointNodes.first().click();

    const forkButton = page.getByRole("button", {
      name: "Fork from this checkpoint",
    });
    await expect(forkButton).toBeVisible({ timeout: 15_000 });
    await forkButton.click();

    await expect(page).toHaveURL(/\?branch=/, { timeout: 15_000 });

    await expect(composer).toBeVisible({ timeout: 15_000 });
    await composer.click();
    await composer.pressSequentially("Focus on liver-stage genes only", {
      delay: 15,
    });
    await expect(sendButton).toBeEnabled({ timeout: 15_000 });
    await composer.press("Enter");

    await expect(
      page.getByText("[mock] branched response for liver-stage"),
    ).toBeVisible({ timeout: 30_000 });
  });
});
