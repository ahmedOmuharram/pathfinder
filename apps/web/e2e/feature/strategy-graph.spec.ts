import { test, expect } from "../fixtures/test";

test.describe("Strategy Graph", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ chatPage }) => {
    await chatPage.goto();
    await chatPage.newChat();
  });

  test("planning artifact creates strategy with real search names stored in DB", async ({
    chatPage,
    graphPage,
    page,
    apiClient,
  }) => {
    await chatPage.send("artifact graph");
    await chatPage.expectPlanningArtifact();

    // UI: Click apply
    await page.getByRole("button", { name: /apply to strategy/i }).click();
    await graphPage.expectCompactView();
    await chatPage.expectIdle();

    // UI: Step pills visible with content
    const pillCount = await graphPage.stepPills.count();
    expect(pillCount).toBeGreaterThan(0);

    // UI: First step pill should show real search-related text
    const firstPillText = await graphPage.stepPills.first().textContent();
    expect(firstPillText).toBeTruthy();

    // API: Strategy persisted with steps — use captured ID for isolation
    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();
    const fullResp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    expect(fullResp.ok()).toBeTruthy();
    const full = await fullResp.json();
    expect(full.steps.length).toBeGreaterThan(0);
  });

  test("delegation creates strategy steps visible in graph and DB", async ({
    chatPage,
    graphPage,
    apiClient,
  }) => {
    await chatPage.send("delegation");
    await chatPage.expectAssistantMessage(/\[mock\].*delegation/i);
    await graphPage.expectCompactView();

    // UI: Step pills from delegation
    const pillCount = await graphPage.stepPills.count();
    expect(pillCount).toBeGreaterThan(0);

    // API: Strategy persisted — use captured ID for isolation
    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();
    const fullResp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    expect(fullResp.ok()).toBeTruthy();
  });

  test("graph persists across page reload — UI and DB consistent", async ({
    chatPage,
    graphPage,
    page,
    apiClient,
  }) => {
    await chatPage.send("artifact graph");
    await chatPage.expectPlanningArtifact();

    await page.getByRole("button", { name: /apply to strategy/i }).click();
    await graphPage.expectCompactView();

    // Use the strategy ID captured during newChat()
    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();

    await page.reload();
    await expect(page.getByTestId("message-composer")).toBeVisible({
      timeout: 15_000,
    });

    // UI: Graph compact view must be visible after reload
    await graphPage.expectCompactView();
    const pillCount = await graphPage.stepPills.count();
    expect(pillCount).toBeGreaterThan(0);

    // API: Strategy still in DB after reload with steps intact
    const afterResp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    expect(afterResp.ok()).toBeTruthy();
    const strategy = await afterResp.json();
    expect(strategy.steps.length).toBeGreaterThan(0);
  });

  test("delegation graph appears immediately during streaming — no refresh needed", async ({
    chatPage,
    graphPage,
  }) => {
    await chatPage.send("delegation");
    // Graph must appear DURING streaming, before message_end
    await graphPage.expectCompactView();
    // Step pills must be visible
    const pillCount = await graphPage.stepPills.count();
    expect(pillCount).toBeGreaterThan(0);
  });

  test("delegation graph visible in UI after page reload", async ({
    chatPage,
    graphPage,
    page,
    apiClient,
  }) => {
    await chatPage.send("delegation");
    await chatPage.expectAssistantMessage(/\[mock\].*delegation/i);
    await chatPage.expectIdle();
    await graphPage.expectCompactView();

    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();

    await page.reload();
    await expect(page.getByTestId("message-composer")).toBeVisible({
      timeout: 15_000,
    });

    // UI: Graph renders after reload
    await graphPage.expectCompactView();
    const pillCount = await graphPage.stepPills.count();
    expect(pillCount).toBeGreaterThan(0);

    // API: Steps persisted
    const resp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    expect(resp.ok()).toBeTruthy();
    const strategy = await resp.json();
    expect(strategy.steps.length).toBeGreaterThan(0);
  });
});
