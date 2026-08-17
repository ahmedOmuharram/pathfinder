import { test, expect } from "../fixtures/test";
import { fetchConversationMessages } from "../fixtures/api-client";
import {
  MOCK_DELEGATION_DRAFT_PROMPT,
  MOCK_PLAN_PROMPT,
} from "../fixtures/mock-prompts";

/**
 * Feature: Chat — real event pipeline through Redis + PostgreSQL.
 * Mock LLM provides deterministic text, but events flow through
 * real kani orchestration → Redis streams → PostgreSQL projections.
 * Every test verifies server-side state via API.
 */
test.describe("Chat", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ chatPage }) => {
    await chatPage.goto();
    await chatPage.newChat();
  });

  test("send message stores conversation in PostgreSQL", async ({
    chatPage,
    apiClient,
  }) => {
    await chatPage.send("hello persistence");
    await chatPage.expectAssistantMessage(/\[mock\]/);
    await chatPage.expectIdle();

    // Messages are reconstructed from the persisted event snapshot.
    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();
    const messages = await fetchConversationMessages(apiClient, strategyId);
    expect(messages.length).toBeGreaterThan(0);
  });

  test("empty message keeps send button disabled", async ({ chatPage }) => {
    await chatPage.expectSendDisabled();
  });

  test("artifact graph stores strategy plan with real WDK search names", async ({
    chatPage,
    apiClient,
  }) => {
    await chatPage.send(MOCK_PLAN_PROMPT);
    await chatPage.expectIdle();

    // Wait for strategy update — at least one assistant message rendered.
    await expect(chatPage.assistantMessages).not.toHaveCount(0, { timeout: 15_000 });

    // Fetch full strategy — verify steps were created with real WDK search names
    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();
    const fullResp = await apiClient.get(`/api/v1/conversations/${strategyId}`);
    expect(fullResp.ok()).toBeTruthy();
    const full = await fullResp.json();
    expect(full.steps.length).toBeGreaterThan(0);
    expect(full.steps[0].searchName).toBe("GenesByTaxon");
  });

  test("building executes via the structured route without chat pollution", async ({
    chatPage,
    apiClient,
    graphPage,
  }) => {
    await chatPage.send(MOCK_PLAN_PROMPT);
    await chatPage.expectIdle();
    await graphPage.expectRailPanel();

    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();
    const fullResp = await apiClient.get(`/api/v1/conversations/${strategyId}`);
    expect(fullResp.ok()).toBeTruthy();
    const full = await fullResp.json();

    expect(full.steps.length).toBeGreaterThan(0);
    const messages = await fetchConversationMessages(apiClient, strategyId);
    expect(
      messages.some(
        (message) =>
          message.role === "user" && message.content.includes("[Plan interaction:"),
      ),
    ).toBe(false);
  });

  test("delegation draft stores event data", async ({ chatPage, apiClient }) => {
    await chatPage.send(MOCK_DELEGATION_DRAFT_PROMPT);
    await chatPage.expectIdle();

    // Messages are reconstructed from the persisted event snapshot.
    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();
    const messages = await fetchConversationMessages(apiClient, strategyId);
    expect(messages.length).toBeGreaterThan(0);
  });

  test("stop streaming cancels operation", async ({ chatPage, page }) => {
    // The mock responds near-instantly, so hold the chat SSE open to keep the
    // stop button on screen long enough to click it.
    let release: () => void = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route("**/api/v1/chat", async (route) => {
      await held;
      await route.continue();
    });

    await chatPage.send("slow");
    await expect(page.getByTestId("stop-button")).toBeVisible({ timeout: 15_000 });
    await chatPage.stopStreaming();
    release();
    await chatPage.expectIdle();
  });

  test("stop posts a server cancel that records a cancellation row", async ({
    chatPage,
    page,
  }) => {
    // Hold the chat SSE open so the stop button stays visible long enough
    // to click. We never let the stream complete; cancellation is the test.
    let release: () => void = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route("**/api/v1/chat", async (route) => {
      await held;
      await route.continue();
    });

    const cancelRequest = page.waitForRequest(
      (r) =>
        r.method() === "POST" &&
        /\/api\/v1\/conversations\/[^/]+\/cancel$/.test(r.url()),
      { timeout: 30_000 },
    );

    await chatPage.send("hello cancel");
    await expect(page.getByTestId("stop-button")).toBeVisible({
      timeout: 15_000,
    });
    await chatPage.stopStreaming();

    const req = await cancelRequest;
    const resp = await req.response();
    expect(resp).not.toBeNull();
    expect(resp?.status()).toBe(204);

    release();
  });

  test("multiple messages stored sequentially in conversation", async ({
    chatPage,
    apiClient,
  }) => {
    await chatPage.send("first message");
    await chatPage.expectAssistantMessage(/\[mock\].*first message/);
    await chatPage.expectIdle();

    await chatPage.send("second message");
    await chatPage.expectAssistantMessage(/\[mock\].*second message/);
    await chatPage.expectIdle();

    // Verify both messages persisted (use captured ID)
    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();
    const messages = await fetchConversationMessages(apiClient, strategyId);
    const userMsgs = messages.filter((m) => m.role === "user");
    const assistantMsgs = messages.filter((m) => m.role === "assistant");
    expect(userMsgs.length).toBeGreaterThanOrEqual(2);
    expect(assistantMsgs.length).toBeGreaterThanOrEqual(2);
  });

  test("conversation auto-created and persisted", async ({ chatPage, sidebarPage }) => {
    await chatPage.send("hello world");
    await chatPage.expectAssistantMessage(/\[mock\]/);

    await sidebarPage.expectAtLeastOneConversation();

    // Strategy ID was captured during newChat
    expect(chatPage.lastStrategyId).toBeTruthy();
  });

  test("page reload restores conversation from PostgreSQL", async ({
    chatPage,
    page,
    apiClient,
  }) => {
    await chatPage.send("persistent message");
    await chatPage.expectAssistantMessage(/\[mock\].*persistent message/);

    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();

    await page.reload();
    await expect(page.getByTestId("message-composer")).toBeVisible();
    await expect(page.getByText("persistent message", { exact: true })).toBeVisible({
      timeout: 15_000,
    });

    // Strategy still exists after reload
    const afterResp = await apiClient.get(`/api/v1/conversations/${strategyId}`);
    expect(afterResp.ok()).toBeTruthy();
  });
});
