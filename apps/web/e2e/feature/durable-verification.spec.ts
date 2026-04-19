/**
 * Durable verification TaskCard E2E (scope-reduced).
 *
 * Per Phase 7 plan notes: exercising the full interrupt + worker + resume
 * flow in Playwright exceeds the 30s per-test budget. This test instead
 * verifies the frontend behaviour that Phase 7 adds: when the backend emits
 * `data-background-task-started` during a chat SSE stream, the UI mounts
 * `TaskCardPart`, subscribes to the per-task SSE endpoint, and reflects
 * `data-task-progress` + `data-task-completed` chunks into the visible
 * card.
 *
 * Full interrupt+worker+resume coverage lives in the backend integration
 * tests (see `test_dispatcher_interrupt.py`, the `durable/` suite, and
 * `test_events_endpoint.py`).
 *
 * Note: this file intentionally avoids the `ChatPage` page-object model —
 * several of its `data-testid` selectors (`message-composer`,
 * `message-input`, `send-button`) no longer exist in the post-AI-SDK-v6
 * composer and are pre-existing breakage outside this task's scope. The
 * composer is targeted here by its placeholder + accessible submit button
 * name instead.
 */

import { test, expect } from "../fixtures/test";

const TASK_ID = "00000000-0000-0000-0000-0000000000aa";
const BASE_URL = process.env["PLAYWRIGHT_BASE_URL"] ?? "http://localhost:3000";

function sseFrame(obj: unknown): string {
  return `data: ${JSON.stringify(obj)}\n\n`;
}

function uiMessageStreamHeaders(): Record<string, string> {
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

async function openStrategy(context: import("@playwright/test").BrowserContext): Promise<string> {
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

test.describe("Durable verification TaskCard", () => {
  test.describe.configure({ mode: "serial" });

  test("TaskCard renders from data-background-task-started and tracks progress to success", async ({
    page,
    context,
  }) => {
    const strategyId = await openStrategy(context);

    const chatStream = [
      sseFrame({
        type: "start",
        messageId: "11111111-1111-1111-1111-111111111111",
        messageMetadata: {
          phase: "verification",
          model: "mock:deterministic",
          traceId: "mock-trace",
          createdAt: new Date().toISOString(),
        },
      }),
      sseFrame({
        type: "data-background-task-started",
        data: {
          taskId: TASK_ID,
          toolName: "run_control_tests_on_step",
          estimatedDurationSeconds: 3,
        },
      }),
      sseFrame({ type: "finish", finishReason: "stop" }),
      "data: [DONE]\n\n",
    ].join("");

    await page.route("**/api/v1/chat", async (route) => {
      await route.fulfill({
        status: 200,
        headers: uiMessageStreamHeaders(),
        body: chatStream,
      });
    });

    await page.route(
      `**/api/v1/conversations/*/tasks/${TASK_ID}/events`,
      async (route) => {
        const payload = [
          sseFrame({
            type: "data-task-progress",
            data: { taskId: TASK_ID, percent: 0.33, message: "Querying WDK step" },
          }),
          sseFrame({
            type: "data-task-progress",
            data: { taskId: TASK_ID, percent: 0.66, message: "Comparing controls" },
          }),
          sseFrame({
            type: "data-task-progress",
            data: { taskId: TASK_ID, percent: 0.99, message: "Exporting results" },
          }),
          sseFrame({
            type: "data-task-completed",
            data: { taskId: TASK_ID, status: "success" },
          }),
          "data: [DONE]\n\n",
        ].join("");
        await route.fulfill({
          status: 200,
          headers: uiMessageStreamHeaders(),
          body: payload,
        });
      },
    );

    await page.goto(`/conversation/${strategyId}`);
    const composer = page.getByPlaceholder("Ask anything", { exact: false });
    await expect(composer).toBeVisible({ timeout: 30_000 });
    const submit = page.getByRole("button", { name: /Submit/i });
    await composer.click();
    await composer.pressSequentially("kick off durable verification", {
      delay: 15,
    });
    await expect(submit).toBeEnabled({ timeout: 15_000 });
    await composer.press("Enter");

    const card = page.getByTestId("task-card");
    await expect(card).toBeVisible({ timeout: 20_000 });
    await expect(card).toContainText("run_control_tests_on_step");

    await expect(card).toHaveAttribute("data-status", "success", {
      timeout: 15_000,
    });
    await expect(card).toContainText(/Completed in/);
  });
});
