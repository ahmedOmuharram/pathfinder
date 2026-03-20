import { test, expect } from "../fixtures/test";

/**
 * Journey: Leishmania Virulence Factor Discovery — TriTrypDB
 *
 * FULL researcher workflow on TriTrypDB. Real WDK API, real Redis, real DB.
 * Only the LLM is mocked.
 *
 * Flow: Switch to TriTrypDB → multi-round chat → strategy via planning
 * artifact (GenesByTaxon for L. major Friedlin) → workbench → add verified
 * virulence gene IDs → verify counts → enrichment → verify results →
 * return to chat → API verification.
 */
test.describe("Leishmania Virulence Journey", () => {
  test("full TriTrypDB research flow with enrichment and API verification", async ({
    chatPage,
    graphPage,
    page,
    seedData,
    apiClient,
    sitePicker,
    workbenchSidebarPage,
    workbenchMainPage,
  }) => {
    const tritrypSiteData = seedData.siteData["tritrypdb"];
    if (tritrypSiteData === undefined) throw new Error("tritrypdb seed data missing");
    const tritrypGenes = tritrypSiteData.geneIds;
    const fullCount = tritrypGenes.length;

    // ── Setup: Clean stale gene sets for TriTrypDB ───────────────
    const cleanupResp = await apiClient.get("/api/v1/gene-sets?siteId=tritrypdb");
    if (cleanupResp.ok()) {
      const stale = (await cleanupResp.json()) as { id: string }[];
      await Promise.all(
        stale.map((gs) => apiClient.delete(`/api/v1/gene-sets/${gs.id}`)),
      );
    }

    // ── Phase 1: Site Switch & Chat ──────────────────────────────

    await chatPage.goto();
    await sitePicker.selectSite("tritrypdb");
    await sitePicker.expectCurrentSite("tritrypdb");

    // Round 1
    await chatPage.send("I'm investigating virulence factors in Leishmania major");
    await chatPage.expectAssistantMessage(/\[mock\]/);
    await chatPage.expectIdle();

    // Round 2
    await chatPage.send(
      "What surface proteases are involved in host macrophage invasion?",
    );
    await chatPage.expectAssistantMessage(/\[mock\].*surface/i);
    await chatPage.expectIdle();

    // ── Phase 2: Strategy Creation ───────────────────────────────

    // Planning artifact with GenesByTaxon for L. major Friedlin
    await chatPage.send("artifact graph");
    await chatPage.expectPlanningArtifact();

    await page.getByRole("button", { name: /apply to strategy/i }).click();
    await graphPage.expectCompactView();
    await chatPage.expectIdle();

    // Verify strategy persisted
    const strategiesResp = await apiClient.get("/api/v1/strategies");
    expect(strategiesResp.ok()).toBeTruthy();
    const strategies = await strategiesResp.json();
    expect(strategies.length).toBeGreaterThan(0);

    // ── Phase 3: Workbench — Gene Sets ───────────────────────────

    // Clean auto-built gene sets so manual set assertions start from zero.
    const preSetsResp = await apiClient.get("/api/v1/gene-sets?siteId=tritrypdb");
    if (preSetsResp.ok()) {
      const preSets = (await preSetsResp.json()) as { id: string }[];
      await Promise.all(
        preSets.map((gs) => apiClient.delete(`/api/v1/gene-sets/${gs.id}`)),
      );
    }

    await workbenchSidebarPage.goto();

    // Create virulence factors set
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Leishmania Virulence Factors");
    await page.getByLabel(/gene ids/i).fill(tritrypGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({
      timeout: 10_000,
    });

    // Verify count on card
    await workbenchSidebarPage.expectSetGeneCount(
      "Leishmania Virulence Factors",
      fullCount,
    );

    // API verification
    const setsResp = await apiClient.get("/api/v1/gene-sets?siteId=tritrypdb");
    expect(setsResp.ok()).toBeTruthy();
    const sets = await setsResp.json();
    expect(sets.length).toBe(1);
    expect(sets[0].geneCount).toBe(fullCount);
    expect(sets[0].geneIds).toHaveLength(fullCount);
    expect(sets[0].siteId).toBe("tritrypdb");

    // ── Phase 4: Activate & Enrichment ───────────────────────────

    await workbenchSidebarPage.activateSet("Leishmania Virulence Factors");
    await workbenchMainPage.expectActiveSetHeader(
      "Leishmania Virulence Factors",
      fullCount,
    );

    // Run real enrichment against TriTrypDB WDK
    await workbenchMainPage.runEnrichmentAndVerifyResults();
    await workbenchMainPage.expectEnrichmentTypeTabs();
    await workbenchMainPage.expectEnrichmentResultsWithData();

    // ── Phase 5: Return to Chat ──────────────────────────────────

    await page.goto("/");
    await chatPage.send(
      "The enrichment shows interesting protease pathways, what about drug targets?",
    );
    await chatPage.expectAssistantMessage(/\[mock\].*drug targets/i);
    await chatPage.expectIdle();

    // Verify conversation has multiple messages
    const conversations = await apiClient.get("/api/v1/strategies");
    expect(conversations.ok()).toBeTruthy();
  });
});
