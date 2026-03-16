import { test, expect } from "../fixtures/test";

/**
 * Journey: Cross-Species Ortholog Comparison — PlasmoDB → ToxoDB
 *
 * FULL researcher workflow comparing genes across species. Real WDK API,
 * real Redis, real DB. Only the LLM is mocked.
 *
 * Flow: PlasmoDB chat → create gene set → verify API → switch to ToxoDB →
 * chat → create gene set → verify per-site isolation via API → switch back →
 * verify PlasmoDB data persisted → run enrichment on PlasmoDB set.
 */
test.describe("Cross-Species Orthologs Journey", () => {
  test("build gene sets on two sites, verify isolation and persistence", async ({
    chatPage,
    page,
    seedData,
    apiClient,
    sitePicker,
    workbenchSidebarPage,
    workbenchMainPage,
  }) => {
    const plasmoGenes = seedData.siteData.plasmodb.geneIds;
    const toxoGenes = seedData.siteData.toxodb.geneIds;

    // ── Setup: Clean stale gene sets for both sites ──────────────
    const cleanupSites = ["plasmodb", "toxodb"];
    await Promise.all(
      cleanupSites.map(async (site) => {
        const resp = await apiClient.get(`/api/v1/gene-sets?siteId=${site}`);
        if (resp.ok()) {
          const stale = (await resp.json()) as { id: string }[];
          await Promise.all(
            stale.map((gs) => apiClient.delete(`/api/v1/gene-sets/${gs.id}`)),
          );
        }
      }),
    );

    // ── Phase 1: PlasmoDB — Chat & Gene Set ──────────────────────

    await chatPage.goto();
    await sitePicker.selectSite("plasmodb");

    // Multi-round chat
    await chatPage.send(
      "I'm comparing drug resistance genes across Plasmodium and Toxoplasma",
    );
    await chatPage.expectAssistantMessage(/\[mock\]/);
    await chatPage.expectIdle();

    await chatPage.send("First let me focus on P. falciparum resistance markers");
    await chatPage.expectAssistantMessage(/\[mock\].*resistance/i);
    await chatPage.expectIdle();

    // Create PlasmoDB gene set
    await workbenchSidebarPage.goto();
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Plasmo Resistance");
    await page.getByLabel(/gene ids/i).fill(plasmoGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({
      timeout: 10_000,
    });

    // Verify count and API persistence
    await workbenchSidebarPage.expectSetGeneCount(
      "Plasmo Resistance",
      plasmoGenes.length,
    );

    const plasmoSetsResp = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    expect(plasmoSetsResp.ok()).toBeTruthy();
    const plasmoSets = await plasmoSetsResp.json();
    expect(plasmoSets.length).toBeGreaterThanOrEqual(1);
    expect(
      plasmoSets.find((gs: { name: string }) => gs.name === "Plasmo Resistance"),
    ).toBeDefined();

    // Activate and verify header
    await workbenchSidebarPage.activateSet("Plasmo Resistance");
    await workbenchMainPage.expectActiveSetHeader(
      "Plasmo Resistance",
      plasmoGenes.length,
    );

    // Run enrichment on PlasmoDB set
    await workbenchMainPage.runEnrichmentAndVerifyResults();
    await workbenchMainPage.expectEnrichmentResultsWithData();

    // ── Phase 2: Switch to ToxoDB ────────────────────────────────

    await sitePicker.selectSite("toxodb");
    await sitePicker.expectCurrentSite("toxodb");

    // Chat on ToxoDB
    await page.goto("/");
    await chatPage.send(
      "Now looking at T. gondii invasion proteins for cross-species comparison",
    );
    await chatPage.expectAssistantMessage(/\[mock\]/);
    await chatPage.expectIdle();

    // Clean auto-built ToxoDB gene sets so manual set assertions start from zero.
    const toxoCleanResp = await apiClient.get("/api/v1/gene-sets?siteId=toxodb");
    if (toxoCleanResp.ok()) {
      const toxoStale = (await toxoCleanResp.json()) as { id: string }[];
      await Promise.all(
        toxoStale.map((gs) => apiClient.delete(`/api/v1/gene-sets/${gs.id}`)),
      );
    }

    // Workbench should be empty — PlasmoDB sets don't leak
    await workbenchSidebarPage.goto();
    await workbenchSidebarPage.expectEmptyState();

    // API confirms no ToxoDB sets exist yet
    const toxoEmptyResp = await apiClient.get("/api/v1/gene-sets?siteId=toxodb");
    const toxoEmpty = await toxoEmptyResp.json();
    expect(toxoEmpty.length).toBe(0);

    // Create ToxoDB gene set
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Toxo Invasion");
    await page.getByLabel(/gene ids/i).fill(toxoGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({
      timeout: 10_000,
    });

    await workbenchSidebarPage.expectSetGeneCount("Toxo Invasion", toxoGenes.length);

    // API confirms ToxoDB set created
    const toxoSetsResp = await apiClient.get("/api/v1/gene-sets?siteId=toxodb");
    const toxoSets = await toxoSetsResp.json();
    expect(toxoSets.length).toBe(1);
    expect(toxoSets[0].siteId).toBe("toxodb");
    expect(toxoSets[0].geneCount).toBe(toxoGenes.length);

    // ── Phase 3: Return to PlasmoDB — Verify Isolation ───────────

    await sitePicker.selectSite("plasmodb");
    await sitePicker.expectCurrentSite("plasmodb");

    // Remove auto-built gene sets, keeping only the manually created one.
    const plasmoCleanResp = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    if (plasmoCleanResp.ok()) {
      const plasmoAll = (await plasmoCleanResp.json()) as {
        id: string;
        name: string;
      }[];
      await Promise.all(
        plasmoAll
          .filter((gs) => gs.name !== "Plasmo Resistance")
          .map((gs) => apiClient.delete(`/api/v1/gene-sets/${gs.id}`)),
      );
    }

    await workbenchSidebarPage.goto();

    // PlasmoDB set should still exist
    await workbenchSidebarPage.expectSetCount(1);
    await workbenchSidebarPage.activateSet("Plasmo Resistance");
    await workbenchMainPage.expectActiveSetHeader(
      "Plasmo Resistance",
      plasmoGenes.length,
    );

    // API confirms PlasmoDB set still intact
    const plasmoVerifyResp = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    const plasmoVerify = await plasmoVerifyResp.json();
    const resistanceSet = plasmoVerify.find(
      (gs: { name: string }) => gs.name === "Plasmo Resistance",
    );
    expect(resistanceSet).toBeDefined();
    expect(resistanceSet.geneCount).toBe(plasmoGenes.length);
  });
});
