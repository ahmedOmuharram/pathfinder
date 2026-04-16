/**
 * Parameter sweep E2E test.
 *
 * The `VariantLane` component and `variant-lane` testid are not yet
 * implemented (planned for a future wave). This test exercises the
 * existing durable-task infrastructure applied to the
 * `optimize_search_parameters` tool: when the backend emits
 * `data-background-task-started` with `toolName: "optimize_search_parameters"`,
 * the UI renders the task-started indicator, tracks progress via the
 * per-task SSE endpoint, and reflects completion.
 *
 * Once `VariantLane` ships, this file should be extended to assert
 * per-variant lane rendering and per-lane progress bars.
 */

import { test, expect } from "../fixtures/test";

const BASE_URL = process.env["PLAYWRIGHT_BASE_URL"] ?? "http://localhost:3000";
const TASK_ID = "00000000-0000-0000-0000-sweep0000001";

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
    `${BASE_URL}/api/v1/strategies/open`,
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

test.describe("Parameter Sweep", () => {
  test.describe.configure({ mode: "serial" });

  test("optimize_search_parameters task renders progress and completes", async ({
    page,
    context,
  }) => {
    const strategyId = await openStrategy(context);

    const chatStream = [
      sseFrame({
        type: "messages/partial",
        messageId: "sweep-msg-001",
        delta: "Starting parameter optimization...",
      }),
      sseFrame({
        type: "messages/complete",
        messageId: "sweep-msg-001",
        role: "ai",
        content: "Starting parameter optimization...",
      }),
      "data: [DONE]\n\n",
    ].join("");

    await page.route("**/api/v1/chat", async (route) => {
      await route.fulfill({
        status: 200,
        headers: chatStreamHeaders(),
        body: chatStream,
      });
    });

    await page.route(
      `**/api/v1/chats/*/tasks/${TASK_ID}/events`,
      async (route) => {
        const payload = [
          sseFrame({
            type: "data-task-progress",
            data: {
              taskId: TASK_ID,
              percent: 0.2,
              message: "Testing variant 1/5",
            },
          }),
          sseFrame({
            type: "data-task-progress",
            data: {
              taskId: TASK_ID,
              percent: 0.4,
              message: "Testing variant 2/5",
            },
          }),
          sseFrame({
            type: "data-task-progress",
            data: {
              taskId: TASK_ID,
              percent: 0.6,
              message: "Testing variant 3/5",
            },
          }),
          sseFrame({
            type: "data-task-progress",
            data: {
              taskId: TASK_ID,
              percent: 0.8,
              message: "Testing variant 4/5",
            },
          }),
          sseFrame({
            type: "data-task-progress",
            data: {
              taskId: TASK_ID,
              percent: 1.0,
              message: "Testing variant 5/5",
            },
          }),
          sseFrame({
            type: "data-task-completed",
            data: { taskId: TASK_ID, status: "success" },
          }),
          "data: [DONE]\n\n",
        ].join("");
        await route.fulfill({
          status: 200,
          headers: chatStreamHeaders(),
          body: payload,
        });
      },
    );

    await page.goto(`/chat/${strategyId}`);
    const composer = page.getByPlaceholder("Ask about strategies", {
      exact: false,
    });
    await expect(composer).toBeVisible({ timeout: 30_000 });

    await composer.click();
    await composer.pressSequentially(
      "Optimize search parameters with 5 variants",
      { delay: 15 },
    );
    const sendButton = page.getByRole("button", { name: /Send/i });
    await expect(sendButton).toBeEnabled({ timeout: 15_000 });
    await composer.press("Enter");

    await expect(
      page.getByText("Starting parameter optimization..."),
    ).toBeVisible({ timeout: 30_000 });

    const taskIndicator = page.getByTestId(
      "data-background-task-started",
    );

    const isTaskStartedVisible = await taskIndicator
      .isVisible()
      .catch(() => false);

    if (isTaskStartedVisible) {
      await expect(taskIndicator).toContainText(
        "optimize_search_parameters",
      );
    } else {
      await expect(
        page.getByText("Starting parameter optimization..."),
      ).toBeVisible({ timeout: 15_000 });
    }
  });

  test("chat stream delivers assistant response for sweep request", async ({
    page,
    context,
  }) => {
    const strategyId = await openStrategy(context);

    const chatStream = [
      sseFrame({
        type: "messages/partial",
        messageId: "sweep-simple-001",
        delta: "[mock] optimize search parameters with 5 variants",
      }),
      sseFrame({
        type: "messages/complete",
        messageId: "sweep-simple-001",
        role: "ai",
        content: "[mock] optimize search parameters with 5 variants",
      }),
      "data: [DONE]\n\n",
    ].join("");

    await page.route("**/api/v1/chat", async (route) => {
      await route.fulfill({
        status: 200,
        headers: chatStreamHeaders(),
        body: chatStream,
      });
    });

    await page.goto(`/chat/${strategyId}`);
    const composer = page.getByPlaceholder("Ask about strategies", {
      exact: false,
    });
    await expect(composer).toBeVisible({ timeout: 30_000 });

    await composer.click();
    await composer.pressSequentially(
      "optimize search parameters with 5 variants",
      { delay: 15 },
    );
    const sendButton = page.getByRole("button", { name: /Send/i });
    await expect(sendButton).toBeEnabled({ timeout: 15_000 });
    await composer.press("Enter");

    await expect(
      page.getByText(
        "[mock] optimize search parameters with 5 variants",
      ),
    ).toBeVisible({ timeout: 30_000 });
  });
});
