import { test, expect } from "../fixtures/test";
import { MOCK_DELEGATION_PROMPT, MOCK_PLAN_PROMPT } from "../fixtures/mock-prompts";

test.describe("AI Workbench Integration", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ chatPage }) => {
    await chatPage.goto();
    await chatPage.newChat();
  });

  test("delegation creates strategy with steps visible in graph and stored in DB", async ({
    chatPage,
    graphPage,
    apiClient,
  }) => {
    await chatPage.send(MOCK_DELEGATION_PROMPT);
    await chatPage.expectPlanningArtifact();
    await chatPage.approvePlan();
    await chatPage.expectIdle();

    // UI: Compact view with step pills
    await graphPage.expectRailPanel();
    const pillCount = await graphPage.railStepRows.count();
    expect(pillCount).toBeGreaterThan(0);

    // API: Strategy persisted — use captured ID for isolation
    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();
    const fullResp = await apiClient.get(`/api/v1/conversations/${strategyId}`);
    expect(fullResp.ok()).toBeTruthy();
    const full = await fullResp.json();
    expect(full.messages).toBeDefined();
    expect(full.messages.length).toBeGreaterThan(0);
  });

  test("artifact graph creates exportable strategy persisted in DB", async ({
    chatPage,
    graphPage,
    page,
    apiClient,
  }) => {
    await chatPage.send(MOCK_PLAN_PROMPT);
    await chatPage.expectPlanningArtifact();

    await chatPage.approvePlan();
    await graphPage.expectRailPanel();
    await chatPage.expectIdle();

    // UI: Edit button visible
    await expect(page.getByRole("button", { name: /edit/i })).toBeVisible();

    // UI: Step pills show content
    const pillCount = await graphPage.railStepRows.count();
    expect(pillCount).toBeGreaterThan(0);

    // API: Strategy with steps persisted — use captured ID for isolation
    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();
    const fullResp = await apiClient.get(`/api/v1/conversations/${strategyId}`);
    expect(fullResp.ok()).toBeTruthy();
    const full = await fullResp.json();
    expect(full.steps.length).toBeGreaterThan(0);
  });
});
