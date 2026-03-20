import { test, expect } from "../fixtures/test";

/**
 * Journey: Toxoplasma Host Cell Invasion — ToxoDB
 *
 * FULL researcher workflow on ToxoDB. Real WDK API, real Redis, real DB.
 * Only the LLM is mocked.
 *
 * Flow: Switch to ToxoDB → multi-round chat → strategy via planning
 * artifact (GenesByTaxon for T. gondii ME49) → workbench → add verified
 * invasion marker gene IDs → verify gene counts → run enrichment → verify
 * real GO terms → set operations → API verification.
 */
test.describe("Toxoplasma Host Invasion Journey", () => {
  test("full ToxoDB research flow with enrichment verification", async ({
    chatPage,
    graphPage,
    page,
    seedData,
    apiClient,
    sitePicker,
    workbenchSidebarPage,
    workbenchMainPage,
  }) => {
    const toxoSiteData = seedData.siteData["toxodb"];
    if (toxoSiteData === undefined) throw new Error("toxodb seed data missing");
    const toxoGenes = toxoSiteData.geneIds;
    const fullCount = toxoGenes.length;
    const subsetGenes = toxoGenes.slice(0, 2);
    const subsetCount = subsetGenes.length;

    // ── Setup: Clean stale gene sets for ToxoDB ──────────────────
    const cleanupResp = await apiClient.get("/api/v1/gene-sets?siteId=toxodb");
    if (cleanupResp.ok()) {
      const stale = (await cleanupResp.json()) as { id: string }[];
      await Promise.all(
        stale.map((gs) => apiClient.delete(`/api/v1/gene-sets/${gs.id}`)),
      );
    }

    // ── Phase 1: Site Switch & Multi-round Chat ──────────────────

    await chatPage.goto();
    await sitePicker.selectSite("toxodb");
    await sitePicker.expectCurrentSite("toxodb");

    // Round 1
    await chatPage.send(
      "I'm studying host cell invasion mechanisms in Toxoplasma gondii",
    );
    await chatPage.expectAssistantMessage(/\[mock\]/);
    await chatPage.expectIdle();

    // Round 2
    await chatPage.send(
      "What micronemal and rhoptry proteins are involved in attachment?",
    );
    await chatPage.expectAssistantMessage(/\[mock\].*micronemal/i);
    await chatPage.expectIdle();

    // Round 3 — trigger planning artifact (GenesByTaxon for T. gondii ME49)
    await chatPage.send("artifact graph");
    await chatPage.expectPlanningArtifact();

    // ── Phase 2: Strategy Creation ───────────────────────────────

    await page.getByRole("button", { name: /apply to strategy/i }).click();
    await graphPage.expectCompactView();
    await chatPage.expectIdle();

    // Verify strategy persisted
    const strategiesResp = await apiClient.get("/api/v1/strategies?siteId=toxodb");
    expect(strategiesResp.ok()).toBeTruthy();

    // ── Phase 3: Workbench — Gene Sets ───────────────────────────

    // Clean auto-built gene sets so manual set assertions start from zero.
    const preSetsResp = await apiClient.get("/api/v1/gene-sets?siteId=toxodb");
    if (preSetsResp.ok()) {
      const preSets = (await preSetsResp.json()) as { id: string }[];
      await Promise.all(
        preSets.map((gs) => apiClient.delete(`/api/v1/gene-sets/${gs.id}`)),
      );
    }

    await workbenchSidebarPage.goto();

    // Create full invasion machinery set
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Invasion Machinery");
    await page.getByLabel(/gene ids/i).fill(toxoGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({
      timeout: 10_000,
    });

    // Verify gene count on card
    await workbenchSidebarPage.expectSetGeneCount("Invasion Machinery", fullCount);

    // Create rhoptry subset
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Rhoptry Subset");
    await page.getByLabel(/gene ids/i).fill(subsetGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({
      timeout: 10_000,
    });

    await workbenchSidebarPage.expectSetGeneCount("Rhoptry Subset", subsetCount);
    await workbenchSidebarPage.expectSetCount(2);

    // API verification — both sets persisted with correct counts
    const setsResp = await apiClient.get("/api/v1/gene-sets?siteId=toxodb");
    expect(setsResp.ok()).toBeTruthy();
    const sets = await setsResp.json();
    expect(sets.length).toBe(2);
    const invasionSet = sets.find(
      (gs: { name: string }) => gs.name === "Invasion Machinery",
    );
    expect(invasionSet.geneCount).toBe(fullCount);
    expect(invasionSet.geneIds).toHaveLength(fullCount);
    expect(invasionSet.siteId).toBe("toxodb");

    // ── Phase 4: Activate & Enrichment ───────────────────────────

    await workbenchSidebarPage.activateSet("Invasion Machinery");
    await workbenchMainPage.expectActiveSetHeader("Invasion Machinery", fullCount);

    // Run real enrichment against ToxoDB WDK
    await workbenchMainPage.runEnrichmentAndVerifyResults();
    await workbenchMainPage.expectEnrichmentTypeTabs();
    await workbenchMainPage.expectEnrichmentResultsWithData();

    // ── Phase 5: Set Operation — Union ────────────────────────────

    await workbenchSidebarPage.selectSet("Invasion Machinery");
    await workbenchSidebarPage.selectSet("Rhoptry Subset");

    await expect(page.getByRole("button", { name: /union/i })).toBeVisible({
      timeout: 10_000,
    });

    // Union of a set with its subset = the full set count
    await workbenchSidebarPage.expectComposeResultCount(fullCount);

    await workbenchSidebarPage.performOperation("union");
    await workbenchSidebarPage.expectSetCount(3);

    // Verify derived set via API
    const updatedResp = await apiClient.get("/api/v1/gene-sets?siteId=toxodb");
    const updatedSets = await updatedResp.json();
    const derivedSet = updatedSets.find(
      (gs: { source: string }) => gs.source === "derived",
    );
    expect(derivedSet).toBeDefined();
    expect(derivedSet.geneCount).toBe(fullCount);
  });
});
