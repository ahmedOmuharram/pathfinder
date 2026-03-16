import { test, expect } from "../fixtures/test";

/**
 * Journey: Malaria Drug Resistance Research — PlasmoDB
 *
 * FULL researcher workflow. Real WDK API, real Redis, real PostgreSQL.
 * Only the LLM is mocked (PATHFINDER_CHAT_PROVIDER=mock).
 *
 * Flow: Auth → multi-round chat → strategy via planning artifact (real
 * GenesByTaxon search) → workbench → create gene sets with verified
 * PlasmoDB gene IDs → run enrichment (real WDK enrichment API) → verify
 * GO terms and counts → set operations → verify derived set counts →
 * API verification of persistence.
 */
test.describe("Malaria Drug Resistance Journey", () => {
  test("complete research flow from chat through enrichment analysis", async ({
    chatPage,
    graphPage,
    page,
    seedData,
    apiClient,
    workbenchSidebarPage,
    workbenchMainPage,
    sitePicker,
  }) => {
    const plasmoGenes = seedData.plasmoGenes;
    const fullCount = plasmoGenes.length;
    const subsetGenes = plasmoGenes.slice(0, 2);
    const subsetCount = subsetGenes.length;

    // ── Setup: Clean stale gene sets for PlasmoDB ────────────────
    const cleanupResp = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    if (cleanupResp.ok()) {
      const stale = (await cleanupResp.json()) as { id: string }[];
      await Promise.all(
        stale.map((gs) => apiClient.delete(`/api/v1/gene-sets/${gs.id}`)),
      );
    }

    // ── Phase 1: Multi-round Chat ─────────────────────────────────

    await chatPage.goto();
    await sitePicker.selectSite("plasmodb");

    // Round 1
    await chatPage.send(
      "I'm investigating chloroquine resistance mechanisms in Plasmodium falciparum",
    );
    await chatPage.expectAssistantMessage(/\[mock\]/);
    await chatPage.expectIdle();

    // Round 2
    await chatPage.send("Can you help me find genes involved in drug resistance?");
    await chatPage.expectAssistantMessage(/\[mock\].*Can you help/);
    await chatPage.expectIdle();

    // Round 3 — trigger planning artifact (real GenesByTaxon search)
    await chatPage.send("artifact graph");
    await chatPage.expectPlanningArtifact();

    // ── Phase 2: Strategy Creation ────────────────────────────────

    // Apply plan — backend stores real strategy with GenesByTaxon search
    await page.getByRole("button", { name: /apply to strategy/i }).click();
    await graphPage.expectCompactView();
    await chatPage.expectIdle();

    // Verify strategy was persisted via API
    const strategiesResp = await apiClient.get("/api/v1/strategies");
    expect(strategiesResp.ok()).toBeTruthy();
    const strategies = await strategiesResp.json();
    expect(strategies.length).toBeGreaterThan(0);

    // ── Phase 3: Workbench — Gene Set Creation ────────────────────

    // Clean auto-built gene sets so manual set assertions start from zero.
    const preSetsResp = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    if (preSetsResp.ok()) {
      const preSets = (await preSetsResp.json()) as { id: string }[];
      await Promise.all(
        preSets.map((gs) => apiClient.delete(`/api/v1/gene-sets/${gs.id}`)),
      );
    }

    await workbenchSidebarPage.goto();

    // Create full resistance markers set
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Drug Resistance Markers");
    await page.getByLabel(/gene ids/i).fill(plasmoGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({
      timeout: 10_000,
    });

    // Verify gene count on the card
    await workbenchSidebarPage.expectSetGeneCount("Drug Resistance Markers", fullCount);

    // Create subset for comparison
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("CRT & Kelch13");
    await page.getByLabel(/gene ids/i).fill(subsetGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({
      timeout: 10_000,
    });

    await workbenchSidebarPage.expectSetGeneCount("CRT & Kelch13", subsetCount);
    await workbenchSidebarPage.expectSetCount(2);

    // Verify gene sets persisted via API
    const geneSetsResp = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    expect(geneSetsResp.ok()).toBeTruthy();
    const geneSets = await geneSetsResp.json();
    expect(geneSets.length).toBe(2);
    const fullSet = geneSets.find(
      (gs: { name: string }) => gs.name === "Drug Resistance Markers",
    );
    expect(fullSet).toBeDefined();
    expect(fullSet.geneCount).toBe(fullCount);
    expect(fullSet.geneIds).toHaveLength(fullCount);

    // ── Phase 4: Activate & Verify Header ─────────────────────────

    await workbenchSidebarPage.activateSet("Drug Resistance Markers");
    await workbenchMainPage.expectActiveSetHeader("Drug Resistance Markers", fullCount);

    // ── Phase 5: Enrichment Analysis (real WDK enrichment API) ────

    // Run enrichment — calls POST /api/v1/gene-sets/{id}/enrich
    // which hits real WDK enrichment service
    await workbenchMainPage.runEnrichmentAndVerifyResults();

    // Verify enrichment type tabs appeared (real GO/Pathway data)
    await workbenchMainPage.expectEnrichmentTypeTabs();

    // Verify actual numbers in the results
    await workbenchMainPage.expectEnrichmentResultsWithData();

    // ── Phase 6: Set Operations with Count Verification ───────────

    await workbenchSidebarPage.selectSet("Drug Resistance Markers");
    await workbenchSidebarPage.selectSet("CRT & Kelch13");

    // Compose bar should show the operation UI
    await expect(page.getByRole("button", { name: /intersect/i })).toBeVisible({
      timeout: 10_000,
    });

    // Preview should show the intersection count (subset is fully
    // contained in the full set, so intersection = subsetCount)
    await workbenchSidebarPage.expectComposeResultCount(subsetCount);

    // Execute intersection
    await workbenchSidebarPage.performOperation("intersect");

    // Verify derived set was created with correct count
    await workbenchSidebarPage.expectSetCount(3);

    // Verify the derived set via API
    const updatedSetsResp = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    const updatedSets = await updatedSetsResp.json();
    expect(updatedSets.length).toBe(3);
    const derivedSet = updatedSets.find(
      (gs: { source: string }) => gs.source === "derived",
    );
    expect(derivedSet).toBeDefined();
    expect(derivedSet.geneCount).toBe(subsetCount);

    // ── Phase 7: Return to Chat ───────────────────────────────────

    await page.goto("/");
    await chatPage.send(
      "Based on the enrichment results, what pathways should I investigate?",
    );
    await chatPage.expectAssistantMessage(/\[mock\].*enrichment/i);
    await chatPage.expectIdle();
  });
});
