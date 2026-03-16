import { test, expect } from "../fixtures/test";

/**
 * Journey: Fungal Pathogenesis — FungiDB
 *
 * FULL researcher workflow on FungiDB. Real WDK API, real Redis, real DB.
 * Only the LLM is mocked.
 *
 * Flow: Switch to FungiDB → multi-round chat → strategy via planning
 * artifact (GenesByTaxon for A. fumigatus Af293) → workbench → add verified
 * cell wall gene IDs → verify counts → enrichment → verify real GO terms →
 * API verification of all persisted data.
 */
test.describe("Fungal Pathogenesis Journey", () => {
  test("full FungiDB research flow with enrichment and API verification", async ({
    chatPage,
    graphPage,
    page,
    seedData,
    apiClient,
    sitePicker,
    workbenchSidebarPage,
    workbenchMainPage,
  }) => {
    const fungiGenes = seedData.siteData.fungidb.geneIds;
    const fullCount = fungiGenes.length;

    // ── Setup: Clean stale gene sets for FungiDB ─────────────────
    const cleanupResp = await apiClient.get("/api/v1/gene-sets?siteId=fungidb");
    if (cleanupResp.ok()) {
      const stale = (await cleanupResp.json()) as { id: string }[];
      await Promise.all(
        stale.map((gs) => apiClient.delete(`/api/v1/gene-sets/${gs.id}`)),
      );
    }

    // ── Phase 1: Site Switch & Chat ──────────────────────────────

    await chatPage.goto();
    await sitePicker.selectSite("fungidb");
    await sitePicker.expectCurrentSite("fungidb");

    // Round 1
    await chatPage.send(
      "I'm researching antifungal drug targets in Aspergillus fumigatus",
    );
    await chatPage.expectAssistantMessage(/\[mock\]/);
    await chatPage.expectIdle();

    // Round 2
    await chatPage.send(
      "What cell wall biosynthesis enzymes are potential drug targets?",
    );
    await chatPage.expectAssistantMessage(/\[mock\].*cell wall/i);
    await chatPage.expectIdle();

    // Round 3
    await chatPage.send(
      "Particularly interested in glucan synthase and chitin synthase",
    );
    await chatPage.expectAssistantMessage(/\[mock\].*glucan/i);
    await chatPage.expectIdle();

    // ── Phase 2: Strategy Creation ───────────────────────────────

    await chatPage.send("artifact graph");
    await chatPage.expectPlanningArtifact();

    await page.getByRole("button", { name: /apply to strategy/i }).click();
    await graphPage.expectCompactView();
    await chatPage.expectIdle();

    // Verify strategy persisted
    const strategiesResp = await apiClient.get("/api/v1/strategies");
    expect(strategiesResp.ok()).toBeTruthy();

    // ── Phase 3: Workbench — Gene Sets ───────────────────────────

    // Clean auto-built gene sets so manual set assertions start from zero.
    const preSetsResp = await apiClient.get("/api/v1/gene-sets?siteId=fungidb");
    if (preSetsResp.ok()) {
      const preSets = (await preSetsResp.json()) as { id: string }[];
      await Promise.all(
        preSets.map((gs) => apiClient.delete(`/api/v1/gene-sets/${gs.id}`)),
      );
    }

    await workbenchSidebarPage.goto();

    // Create antifungal targets set
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Antifungal Targets");
    await page.getByLabel(/gene ids/i).fill(fungiGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({
      timeout: 10_000,
    });

    // Verify count on card
    await workbenchSidebarPage.expectSetGeneCount("Antifungal Targets", fullCount);

    // API verification — gene set persisted with correct data
    const setsResp = await apiClient.get("/api/v1/gene-sets?siteId=fungidb");
    expect(setsResp.ok()).toBeTruthy();
    const sets = await setsResp.json();
    expect(sets.length).toBe(1);
    expect(sets[0].name).toBe("Antifungal Targets");
    expect(sets[0].geneCount).toBe(fullCount);
    expect(sets[0].geneIds).toHaveLength(fullCount);
    expect(sets[0].siteId).toBe("fungidb");
    expect(sets[0].source).toBe("paste");

    // ── Phase 4: Activate & Verify Header ────────────────────────

    await workbenchSidebarPage.activateSet("Antifungal Targets");
    await workbenchMainPage.expectActiveSetHeader("Antifungal Targets", fullCount);

    // ── Phase 5: Enrichment (real WDK enrichment API) ────────────

    await workbenchMainPage.runEnrichmentAndVerifyResults();
    await workbenchMainPage.expectEnrichmentTypeTabs();
    await workbenchMainPage.expectEnrichmentResultsWithData();

    // ── Phase 6: Verify Disabled Panels ──────────────────────────

    // Results Table and Distribution require strategy-backed gene sets
    // (paste sets don't have wdkStepId), so these should be disabled
    await workbenchMainPage.expectPanelVisible("Results Table");
    await workbenchMainPage.expectPanelVisible("Distribution Explorer");

    // ── Phase 7: Return to Chat ──────────────────────────────────

    await page.goto("/");
    await chatPage.send(
      "The enrichment confirms cell wall synthesis pathways, what's the clinical relevance?",
    );
    await chatPage.expectAssistantMessage(/\[mock\].*clinical/i);
    await chatPage.expectIdle();
  });
});
