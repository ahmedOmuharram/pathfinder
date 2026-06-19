import { test, expect } from "../fixtures/test";
import type { BrowserContext } from "@playwright/test";

const TASK_ID = "00000000-0000-0000-0000-0000000000bb";
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
  conversationId?: string;
  strategyId?: string;
  id?: string;
}

async function openStrategy(context: BrowserContext): Promise<string> {
  const resp = await context.request.post(`${BASE_URL}/api/v1/conversations/open`, {
    data: { siteId: "veupathdb" },
    headers: { "X-Requested-With": "XMLHttpRequest" },
  });
  if (!resp.ok()) {
    throw new Error(`openStrategy failed: ${resp.status()}`);
  }
  const body = (await resp.json()) as OpenStrategyResponse;
  const id = body.conversationId ?? body.strategyId ?? body.id;
  if (id === undefined || id === "") {
    throw new Error("openStrategy returned no id");
  }
  return id;
}

test.describe("Durable task live progress", () => {
  test("progress card advances from the per-task SSE channel", async ({
    page,
    context,
  }) => {
    const strategyId = await openStrategy(context);

    const chatStream = [
      sseFrame({
        type: "start",
        messageId: "22222222-2222-2222-2222-222222222222",
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
          estimatedDurationSeconds: 5,
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

    await page.route("**/api/v1/conversations/*/events?*", async (route) => {
      await route.fulfill({ status: 204, body: "" });
    });

    const taskStream = [
      sseFrame({
        type: "data-task-progress",
        data: { taskId: TASK_ID, percent: 0.6, message: "Comparing controls" },
      }),
      "data: [DONE]\n\n",
    ].join("");

    let taskEventsRequested = false;
    await page.route(
      `**/api/v1/conversations/*/tasks/${TASK_ID}/events*`,
      async (route) => {
        taskEventsRequested = true;
        await route.fulfill({
          status: 200,
          headers: uiMessageStreamHeaders(),
          body: taskStream,
        });
      },
    );

    await page.goto(`/conversation/${strategyId}`);
    const composer = page.getByTestId("message-input");
    await expect(composer).toBeVisible({ timeout: 30_000 });
    const submit = page.getByRole("button", { name: /Send/i });
    await composer.click();
    await composer.pressSequentially("kick off durable verification", { delay: 15 });
    await expect(submit).toBeEnabled({ timeout: 15_000 });
    await composer.press("Enter");

    const started = page.getByTestId("data-background-task-started");
    await expect(started).toBeVisible({ timeout: 20_000 });

    await expect.poll(() => taskEventsRequested, { timeout: 15_000 }).toBe(true);

    await expect(page.getByText("Comparing controls")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText("60%")).toBeVisible({ timeout: 15_000 });
  });

  test("fan-out sweep renders one lane per variant from the per-task SSE", async ({
    page,
    context,
  }) => {
    const strategyId = await openStrategy(context);

    const chatStream = [
      sseFrame({
        type: "start",
        messageId: "33333333-3333-3333-3333-333333333333",
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
          toolName: "optimize_search_parameters",
          estimatedDurationSeconds: 900,
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
    await page.route("**/api/v1/conversations/*/events?*", async (route) => {
      await route.fulfill({ status: 204, body: "" });
    });

    const taskStream = [
      sseFrame({
        type: "data-task-progress",
        data: {
          taskId: TASK_ID,
          percent: 0.3,
          message: "Variant A trial 1",
          toolSpecific: { variantId: "variant-A" },
        },
      }),
      sseFrame({
        type: "data-task-progress",
        data: {
          taskId: TASK_ID,
          percent: 0.5,
          message: "Variant B trial 1",
          toolSpecific: { variantId: "variant-B" },
        },
      }),
      "data: [DONE]\n\n",
    ].join("");
    await page.route(
      `**/api/v1/conversations/*/tasks/${TASK_ID}/events*`,
      async (route) => {
        await route.fulfill({
          status: 200,
          headers: uiMessageStreamHeaders(),
          body: taskStream,
        });
      },
    );

    await page.goto(`/conversation/${strategyId}`);
    const composer = page.getByTestId("message-input");
    await expect(composer).toBeVisible({ timeout: 30_000 });
    await composer.click();
    await composer.pressSequentially("optimize the search parameters", { delay: 15 });
    await expect(page.getByRole("button", { name: /Send/i })).toBeEnabled({
      timeout: 15_000,
    });
    await composer.press("Enter");

    await expect(page.getByTestId("data-background-task-started")).toBeVisible({
      timeout: 20_000,
    });

    await expect(page.getByTestId("variant-lane")).toHaveCount(2, {
      timeout: 15_000,
    });
    const laneA = page
      .getByTestId("variant-lane")
      .filter({ hasText: "Variant A trial 1" });
    const laneB = page
      .getByTestId("variant-lane")
      .filter({ hasText: "Variant B trial 1" });
    await expect(laneA.getByText("30%")).toBeVisible({ timeout: 15_000 });
    await expect(laneB.getByText("50%")).toBeVisible({ timeout: 15_000 });
  });
});
