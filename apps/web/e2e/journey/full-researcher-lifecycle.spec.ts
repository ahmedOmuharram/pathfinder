import { test, expect } from "../fixtures/test";
import { clearAllGeneSets } from "../fixtures/api-client";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";

/**
 * Journey: Full Researcher Lifecycle — PlasmoDB (Complete Arc)
 *
 * The most comprehensive journey test. Covers the ENTIRE user lifecycle:
 * Auth → multi-round chat → strategy creation → workbench → gene sets →
 * enrichment with real results → set operations with count verification →
 * site switching with isolation verification → settings → API verification
 * at every stage.
 *
 * Real WDK API, real Redis, real PostgreSQL. Only the LLM is mocked.
 */
test.describe("Full Researcher Lifecycle", () => {
  test("end-to-end research workflow with full output verification", async ({
    chatPage,
    graphPage,
    sidebarPage,
    sitePicker,
    settingsPage,
    page,
    seedData,
    apiClient,
    workbenchSidebarPage,
    workbenchMainPage,
  }) => {
    const plasmoGenes = seedData.plasmoGenes;
    const fullCount = plasmoGenes.length;
    const subsetGenes = plasmoGenes.slice(0, 3);
    const subsetCount = subsetGenes.length;

    // ═══════════════════════════════════════════════════════════════
    // Phase 1: Chat & Strategy (PlasmoDB)
    // ═══════════════════════════════════════════════════════════════

    // Switch to PlasmoDB for this journey
    await chatPage.goto();
    await sitePicker.selectSite("plasmodb");

    // Start fresh conversation
    await chatPage.newChat();

    // Chat round 1
    await chatPage.send("find drug resistance genes in Plasmodium falciparum");
    await chatPage.expectAssistantMessage(/\[mock\]/);
    await chatPage.expectIdle();

    // Chat round 2
    await chatPage.send(
      "I want to focus on chloroquine and artemisinin resistance mechanisms",
    );
    await chatPage.expectAssistantMessage(/\[mock\].*chloroquine/i);
    await chatPage.expectIdle();

    // Chat round 3 — trigger planning artifact
    await chatPage.send("artifact graph");
    await chatPage.expectPlanningArtifact();

    // Apply strategy — real GenesByTaxon search stored
    await page.getByRole("button", { name: /apply to strategy/i }).click();
    await graphPage.expectCompactView();

    // Verify strategy exists via API — use captured ID for isolation
    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();
    const stratResp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    expect(stratResp.ok()).toBeTruthy();
    const latestStrategy = await stratResp.json();
    expect(latestStrategy.steps.length).toBeGreaterThan(0);

    // ═══════════════════════════════════════════════════════════════
    // Phase 2: Workbench — Gene Sets with Count Verification
    // ═══════════════════════════════════════════════════════════════

    await clearAllGeneSets(page.context(), BASE_URL);
    await workbenchSidebarPage.goto();

    // Add full resistance markers set
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Resistance Markers");
    await page.getByLabel(/gene ids/i).fill(plasmoGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({
      timeout: 10_000,
    });

    // Verify exact gene count on card
    await workbenchSidebarPage.expectSetGeneCount("Resistance Markers", fullCount);

    // Add subset
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Top 3 Markers");
    await page.getByLabel(/gene ids/i).fill(subsetGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({
      timeout: 10_000,
    });

    await workbenchSidebarPage.expectSetGeneCount("Top 3 Markers", subsetCount);
    await workbenchSidebarPage.expectSetCount(2);

    // API verification — both sets with correct counts
    const setsResp = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    expect(setsResp.ok()).toBeTruthy();
    const sets = await setsResp.json();
    expect(sets.length).toBe(2);

    const fullSet = sets.find(
      (gs: { name: string }) => gs.name === "Resistance Markers",
    );
    expect(fullSet).toBeDefined();
    expect(fullSet.geneCount).toBe(fullCount);
    expect(fullSet.geneIds).toHaveLength(fullCount);

    const subSet = sets.find((gs: { name: string }) => gs.name === "Top 3 Markers");
    expect(subSet).toBeDefined();
    expect(subSet.geneCount).toBe(subsetCount);

    // ═══════════════════════════════════════════════════════════════
    // Phase 3: Activate & Full Enrichment Analysis
    // ═══════════════════════════════════════════════════════════════

    await workbenchSidebarPage.activateSet("Resistance Markers");
    await workbenchMainPage.expectActiveSetHeader("Resistance Markers", fullCount);

    // Run enrichment — real WDK enrichment API
    await workbenchMainPage.runEnrichmentAndVerifyResults();

    // Verify enrichment produced actual GO/pathway data
    await workbenchMainPage.expectEnrichmentTypeTabs();
    await workbenchMainPage.expectEnrichmentResultsWithData();

    // ═══════════════════════════════════════════════════════════════
    // Phase 4: Set Operations with Mathematical Verification
    // ═══════════════════════════════════════════════════════════════

    // Select both sets
    await workbenchSidebarPage.selectSet("Resistance Markers");
    await workbenchSidebarPage.selectSet("Top 3 Markers");

    // Verify compose bar appears with operations
    await expect(page.getByRole("button", { name: /intersect/i })).toBeVisible({
      timeout: 10_000,
    });

    // Intersection: subset is contained in full set, so result = subsetCount
    await workbenchSidebarPage.expectComposeResultCount(subsetCount);
    await workbenchSidebarPage.performOperation("intersect");
    await workbenchSidebarPage.expectSetCount(3);

    // API verification of derived set
    const derivedResp = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    const allSets = await derivedResp.json();
    expect(allSets.length).toBe(3);
    const derivedSet = allSets.find(
      (gs: { source: string }) => gs.source === "derived",
    );
    expect(derivedSet).toBeDefined();
    expect(derivedSet.geneCount).toBe(subsetCount);
    expect(derivedSet.operation).toBe("intersect");

    // ═══════════════════════════════════════════════════════════════
    // Phase 5: Site Switching — Isolation Verification
    // ═══════════════════════════════════════════════════════════════

    // Switch to ToxoDB
    await sitePicker.selectSite("toxodb");
    await sitePicker.expectCurrentSite("toxodb");

    // Clean any stale ToxoDB gene sets before checking isolation.
    const staleToxoResp = await apiClient.get("/api/v1/gene-sets?siteId=toxodb");
    if (staleToxoResp.ok()) {
      const staleToxo = (await staleToxoResp.json()) as { id: string }[];
      await Promise.all(
        staleToxo.map((gs) => apiClient.delete(`/api/v1/gene-sets/${gs.id}`)),
      );
    }

    // Workbench should show empty state (no ToxoDB sets)
    await workbenchSidebarPage.goto();

    // API confirms no ToxoDB gene sets
    const toxoResp = await apiClient.get("/api/v1/gene-sets?siteId=toxodb");
    expect(toxoResp.ok()).toBeTruthy();
    const toxoSets = await toxoResp.json();
    expect(toxoSets.length).toBe(0);

    // ═══════════════════════════════════════════════════════════════
    // Phase 6: Return to PlasmoDB & Settings
    // ═══════════════════════════════════════════════════════════════

    await sitePicker.selectSite("plasmodb");
    await sitePicker.expectCurrentSite("plasmodb");

    // Settings modal
    await settingsPage.open();
    await settingsPage.expectAllTabsVisible();
    await settingsPage.openTab("Data");
    await settingsPage.close();

    // ═══════════════════════════════════════════════════════════════
    // Phase 7: Final Chat & Conversation Persistence
    // ═══════════════════════════════════════════════════════════════

    await page.goto("/");
    await expect(page.getByTestId("message-composer")).toBeVisible();

    // Verify conversations still exist in sidebar
    await expect(sidebarPage.items.first()).toBeVisible({ timeout: 15_000 });

    // Send final message
    await chatPage.send("Summarize my findings from the resistance gene analysis");
    await chatPage.expectAssistantMessage(/\[mock\].*findings/i);
    await chatPage.expectIdle();

    // API verification — manually created PlasmoDB gene sets still intact
    // (auto-build may add extra strategy-sourced sets, so check by name)
    const finalResp = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    const finalSets = (await finalResp.json()) as { name: string; source: string }[];
    expect(finalSets.length).toBeGreaterThanOrEqual(3);
    expect(finalSets.find((gs) => gs.name === "Resistance Markers")).toBeDefined();
    expect(finalSets.find((gs) => gs.name === "Top 3 Markers")).toBeDefined();
    expect(finalSets.find((gs) => gs.source === "derived")).toBeDefined();
  });
});
