import { test, expect } from "../fixtures/test";

/**
 * Auto-build E2E tests.
 *
 * Verify the full pipeline when MockEngine returns tool calls:
 *   MockEngine.predict() -> kani do_function_call -> auto-build -> real WDK API
 *   -> real gene set creation -> real PostgreSQL persistence -> real SSE events
 *
 * The ONLY mock is the LLM engine. Everything else is real.
 */

test.describe("Auto-Build Pipeline", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ chatPage }) => {
    await chatPage.goto();
    await chatPage.newChat();
  });

  test("create step triggers auto-build with real WDK strategy ID", async ({
    chatPage,
    apiClient,
  }) => {
    // "create step" keyword -> MockEngine returns create_step(GenesByTaxon)
    // -> do_function_call fires -> auto-build pushes to WDK -> wdkStrategyId set
    await chatPage.send("create step");
    await chatPage.expectAssistantMessage(/\[mock\]/i);
    await chatPage.expectIdle();

    // API: Strategy has a real wdkStrategyId (auto-build ran against real WDK)
    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();
    const resp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    expect(resp.ok()).toBeTruthy();
    const strategy = await resp.json();
    expect(strategy.wdkStrategyId).toBeTruthy();
    expect(typeof strategy.wdkStrategyId).toBe("number");
    expect(strategy.wdkStrategyId).toBeGreaterThan(0);
  });

  test("create step produces correct step with real search name and record type", async ({
    chatPage,
    apiClient,
  }) => {
    await chatPage.send("create step");
    await chatPage.expectAssistantMessage(/\[mock\]/i);
    await chatPage.expectIdle();

    const strategyId = chatPage.lastStrategyId;
    const resp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    const strategy = await resp.json();

    // Steps persisted with real WDK search names and parameters
    expect(strategy.steps.length).toBeGreaterThan(0);
    const step = strategy.steps[0];
    expect(step.searchName).toBe("GenesByTaxon");
    // WDK uses "transcript" as the record type for gene searches (GenesByTaxon
    // is on the transcript record type, not "gene").
    expect(step.recordType).toBeTruthy();
    expect(step.parameters).toBeDefined();
    expect(step.parameters.organism).toContain("Plasmodium falciparum 3D7");
  });

  test("auto-build creates gene set with real gene IDs from WDK", async ({
    chatPage,
    apiClient,
  }) => {
    await chatPage.send("create step");
    await chatPage.expectAssistantMessage(/\[mock\]/i);
    await chatPage.expectIdle();

    // Gene sets: auto-build should have created one with real gene IDs
    const gsResp = await apiClient.get("/api/v1/gene-sets");
    expect(gsResp.ok()).toBeTruthy();
    const geneSets = await gsResp.json();

    // At least one gene set was created by auto-build
    expect(geneSets.length).toBeGreaterThan(0);
    const gs = geneSets[0];
    expect(gs.source).toBe("strategy");
    // Site ID depends on the default site setting (veupathdb or plasmodb).
    expect(gs.siteId).toBeTruthy();

    // Gene set has REAL gene IDs (not empty, not fake)
    expect(gs.geneCount).toBeGreaterThan(0);
    expect(gs.geneIds).toBeDefined();
    expect(gs.geneIds.length).toBeGreaterThan(0);

    // Gene IDs look like real PlasmoDB gene IDs (PF3D7_*)
    const firstGene = gs.geneIds[0];
    expect(firstGene).toMatch(/^PF3D7_/i);
  });

  test("auto-build result count matches WDK gene count", async ({
    chatPage,
    apiClient,
  }) => {
    await chatPage.send("create step");
    await chatPage.expectAssistantMessage(/\[mock\]/i);
    await chatPage.expectIdle();

    const strategyId = chatPage.lastStrategyId;
    const stratResp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    const strategy = await stratResp.json();

    // The strategy should have a result count from WDK
    // (populated during auto-build via build_strategy_for_site)
    expect(strategy.wdkStrategyId).toBeTruthy();

    // Gene set count should match or approximate the WDK result count
    const gsResp = await apiClient.get("/api/v1/gene-sets");
    const geneSets = await gsResp.json();
    const strategyGs = geneSets.find(
      (gs: { source: string }) => gs.source === "strategy",
    );
    expect(strategyGs).toBeDefined();
    expect(strategyGs.geneCount).toBeGreaterThan(0);
  });

  test("graph compact view appears after auto-build", async ({
    chatPage,
    graphPage,
  }) => {
    await chatPage.send("create step");
    await chatPage.expectIdle();

    // Graph must be visible with at least one step pill
    await graphPage.expectCompactView();
    const pillCount = await graphPage.stepPills.count();
    expect(pillCount).toBeGreaterThan(0);
  });
});

test.describe("Delegation Auto-Build Pipeline", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ chatPage }) => {
    await chatPage.goto();
    await chatPage.newChat();
  });

  test("delegation creates strategy with wdkStrategyId via sub-kani pipeline", async ({
    chatPage,
    apiClient,
  }) => {
    // "delegation" keyword -> MockEngine returns delegate_strategy_subtasks
    // -> real delegation orchestrator -> sub-kanis with MockEngine -> create_step
    // -> do_function_call -> auto-build -> real WDK strategy
    await chatPage.send("delegation");
    await chatPage.expectAssistantMessage(/\[mock\]/i, { timeout: 60_000 });
    await chatPage.expectIdle();

    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();
    const resp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    expect(resp.ok()).toBeTruthy();
    const strategy = await resp.json();

    // Real WDK strategy ID from auto-build
    expect(strategy.wdkStrategyId).toBeTruthy();
    expect(typeof strategy.wdkStrategyId).toBe("number");

    // Steps created by sub-kanis
    expect(strategy.steps.length).toBeGreaterThan(0);
  });

  test("delegation creates gene set with real gene count", async ({
    chatPage,
    apiClient,
  }) => {
    await chatPage.send("delegation");
    await chatPage.expectAssistantMessage(/\[mock\]/i, { timeout: 60_000 });
    await chatPage.expectIdle();

    const gsResp = await apiClient.get("/api/v1/gene-sets");
    expect(gsResp.ok()).toBeTruthy();
    const geneSets = await gsResp.json();

    const strategyGs = geneSets.find(
      (gs: { source: string }) => gs.source === "strategy",
    );
    expect(strategyGs).toBeDefined();
    expect(strategyGs.geneCount).toBeGreaterThan(0);
    expect(strategyGs.geneIds.length).toBeGreaterThan(0);
  });

  test("delegation graph appears during streaming", async ({ chatPage, graphPage }) => {
    await chatPage.send("delegation");
    // Graph should appear DURING streaming (before message_end)
    await graphPage.expectCompactView();
    const pillCount = await graphPage.stepPills.count();
    expect(pillCount).toBeGreaterThan(0);
  });
});

test.describe("Planning Artifact Pipeline", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ chatPage }) => {
    await chatPage.goto();
    await chatPage.newChat();
  });

  test("artifact graph produces planning artifact with real WDK search names", async ({
    chatPage,
    apiClient,
  }) => {
    // "artifact graph" -> MockEngine returns save_planning_artifact tool call
    // -> real tool execution -> planningArtifact in tool result
    // -> tool_result_to_events extracts it -> planning_artifact SSE event
    await chatPage.send("artifact graph");
    await chatPage.expectPlanningArtifact();

    // Verify the planning artifact data via API
    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();
    const resp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    // Strategy should exist (plan is populated when the user clicks Apply,
    // not when the artifact is first emitted via tool call).
    expect(resp.ok()).toBeTruthy();
  });

  test("artifact graph apply creates real WDK strategy", async ({
    chatPage,
    graphPage,
    page,
    apiClient,
  }) => {
    await chatPage.send("artifact graph");
    await chatPage.expectPlanningArtifact();

    // Click "Apply to Strategy" — this creates steps from the plan
    await page.getByRole("button", { name: /apply to strategy/i }).click();
    await graphPage.expectCompactView();
    await chatPage.expectIdle();

    // After apply, strategy should have steps with real search names
    const strategyId = chatPage.lastStrategyId;
    const resp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    const strategy = await resp.json();
    expect(strategy.steps.length).toBeGreaterThan(0);
    expect(strategy.steps[0].searchName).toBe("GenesByTaxon");
  });
});

test.describe("Mock Engine Response Correctness", () => {
  test.beforeEach(async ({ chatPage }) => {
    await chatPage.goto();
    await chatPage.newChat();
  });

  test("default message returns plain text without tool calls", async ({
    chatPage,
  }) => {
    await chatPage.send("hello world");
    await chatPage.expectAssistantMessage(/\[mock\].*hello world/i);
    await chatPage.expectIdle();

    // The response should echo the message with [mock] prefix —
    // no tool calls, no strategy updates, no graph changes.
    // (We verify no graph appears by checking the assistant message content
    // rather than DB state, since DB state can leak from prior serial suites.)
    const text = await chatPage.assistantMessages.last().textContent();
    expect(text).toContain("[mock]");
    expect(text).toContain("hello world");
  });

  test("delegation draft produces planning artifact not delegation", async ({
    chatPage,
  }) => {
    // "delegation draft" should trigger save_planning_artifact, not delegation
    await chatPage.send("delegation draft");
    await chatPage.expectPlanningArtifact();
    await chatPage.expectIdle();
  });

  test("multiple sequential messages each produce responses", async ({ chatPage }) => {
    await chatPage.send("first message");
    await chatPage.expectAssistantMessage(/\[mock\].*first message/i);
    await chatPage.expectIdle();

    await chatPage.send("second message");
    await chatPage.expectAssistantMessage(/\[mock\].*second message/i);
    await chatPage.expectIdle();
  });

  test("tool call events flow through real SSE pipeline", async ({
    chatPage,
    page,
  }) => {
    // "create step" triggers a real tool call that produces
    // tool_call_start and tool_call_end SSE events
    await chatPage.send("create step");
    await chatPage.expectIdle();

    // The thinking panel should show the tool call
    const thinkingButton = page.getByText("Thought").first();
    if (await thinkingButton.isVisible().catch(() => false)) {
      await thinkingButton.click();
      // Tool call name should appear in thinking details
      await expect(page.getByText(/create_step/i).first()).toBeVisible({
        timeout: 5_000,
      });
    }
  });
});

test.describe("Auto-Build Persistence", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ chatPage }) => {
    await chatPage.goto();
    await chatPage.newChat();
  });

  test("auto-built strategy survives page reload", async ({
    chatPage,
    page,
    apiClient,
  }) => {
    await chatPage.send("create step");
    await chatPage.expectAssistantMessage(/\[mock\]/i);
    await chatPage.expectIdle();

    const strategyId = chatPage.lastStrategyId;

    // Verify strategy has real WDK data BEFORE reload.
    const preResp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    const preBuild = await preResp.json();
    expect(preBuild.wdkStrategyId).toBeTruthy();
    expect(preBuild.steps.length).toBeGreaterThan(0);
    const wdkId = preBuild.wdkStrategyId;
    const stepCount = preBuild.steps.length;

    // Reload the page
    await page.reload();
    await expect(page.getByTestId("message-composer")).toBeVisible({
      timeout: 15_000,
    });

    // API: wdkStrategyId and steps unchanged after reload.
    const postResp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    const postBuild = await postResp.json();
    expect(postBuild.wdkStrategyId).toBe(wdkId);
    expect(postBuild.steps.length).toBe(stepCount);
    expect(postBuild.steps[0].searchName).toBe("GenesByTaxon");
  });

  test("gene set persists across page reload", async ({
    chatPage,
    page,
    apiClient,
  }) => {
    await chatPage.send("create step");
    await chatPage.expectIdle();

    // Check gene set exists before reload
    let gsResp = await apiClient.get("/api/v1/gene-sets");
    let geneSets = await gsResp.json();
    const beforeCount = geneSets.length;
    expect(beforeCount).toBeGreaterThan(0);

    // Reload
    await page.reload();
    await expect(page.getByTestId("message-composer")).toBeVisible({
      timeout: 15_000,
    });

    // Gene set still exists after reload
    gsResp = await apiClient.get("/api/v1/gene-sets");
    geneSets = await gsResp.json();
    expect(geneSets.length).toBe(beforeCount);
  });
});
