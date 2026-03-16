import { test, expect } from "../fixtures/test";

/**
 * Journey: Cryptosporidium Intestinal Infection — CryptoDB
 *
 * FULL researcher workflow on CryptoDB. Real WDK API, real Redis, real DB.
 * Only the LLM is mocked.
 *
 * Flow: Switch to CryptoDB → multi-round chat → strategy via planning
 * artifact (GenesByTaxon for C. parvum Iowa II) → workbench → add verified
 * oocyst wall protein gene IDs → verify counts → enrichment → set operations
 * (minus) → verify derived set count → API verification.
 */
test.describe("Crypto Intestinal Infection Journey", () => {
  test("full CryptoDB research flow with set operations and API verification", async ({
    chatPage,
    graphPage,
    page,
    seedData,
    apiClient,
    sitePicker,
    workbenchSidebarPage,
    workbenchMainPage,
  }) => {
    const cryptoGenes = seedData.siteData.cryptodb.geneIds;
    const fullCount = cryptoGenes.length;
    const subsetGenes = cryptoGenes.slice(0, 2);
    const subsetCount = subsetGenes.length;
    const minusCount = fullCount - subsetCount; // genes in full but not in subset

    // ── Setup: Clean stale gene sets for CryptoDB ────────────────
    const cleanupResp = await apiClient.get("/api/v1/gene-sets?siteId=cryptodb");
    if (cleanupResp.ok()) {
      const stale = (await cleanupResp.json()) as { id: string }[];
      await Promise.all(
        stale.map((gs) => apiClient.delete(`/api/v1/gene-sets/${gs.id}`)),
      );
    }

    // ── Phase 1: Site Switch & Chat ──────────────────────────────

    await chatPage.goto();
    await sitePicker.selectSite("cryptodb");
    await sitePicker.expectCurrentSite("cryptodb");

    // Round 1
    await chatPage.send(
      "I'm studying Cryptosporidium parvum intestinal infection mechanisms",
    );
    await chatPage.expectAssistantMessage(/\[mock\]/);
    await chatPage.expectIdle();

    // Round 2
    await chatPage.send(
      "What oocyst wall proteins are important for environmental survival?",
    );
    await chatPage.expectAssistantMessage(/\[mock\].*oocyst/i);
    await chatPage.expectIdle();

    // ── Phase 2: Strategy Creation ───────────────────────────────

    await chatPage.send("artifact graph");
    await chatPage.expectPlanningArtifact();

    await page.getByRole("button", { name: /apply to strategy/i }).click();
    await graphPage.expectCompactView();
    await chatPage.expectIdle();

    // ── Phase 3: Workbench — Gene Sets ───────────────────────────

    // Clean auto-built gene sets so manual set assertions start from zero.
    const preSetsResp = await apiClient.get("/api/v1/gene-sets?siteId=cryptodb");
    if (preSetsResp.ok()) {
      const preSets = (await preSetsResp.json()) as { id: string }[];
      await Promise.all(
        preSets.map((gs) => apiClient.delete(`/api/v1/gene-sets/${gs.id}`)),
      );
    }

    await workbenchSidebarPage.goto();

    // Create full effectors set
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Crypto Effectors");
    await page.getByLabel(/gene ids/i).fill(cryptoGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({
      timeout: 10_000,
    });

    await workbenchSidebarPage.expectSetGeneCount("Crypto Effectors", fullCount);

    // Create COWP subset
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("COWP Subset");
    await page.getByLabel(/gene ids/i).fill(subsetGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({
      timeout: 10_000,
    });

    await workbenchSidebarPage.expectSetGeneCount("COWP Subset", subsetCount);
    await workbenchSidebarPage.expectSetCount(2);

    // API verification
    const setsResp = await apiClient.get("/api/v1/gene-sets?siteId=cryptodb");
    expect(setsResp.ok()).toBeTruthy();
    const sets = await setsResp.json();
    expect(sets.length).toBe(2);

    // ── Phase 4: Activate & Enrichment ───────────────────────────

    await workbenchSidebarPage.activateSet("Crypto Effectors");
    await workbenchMainPage.expectActiveSetHeader("Crypto Effectors", fullCount);

    // Real enrichment against CryptoDB WDK
    await workbenchMainPage.runEnrichmentAndVerifyResults();
    await workbenchMainPage.expectEnrichmentResultsWithData();

    // ── Phase 5: Set Operation — Minus ───────────────────────────

    await workbenchSidebarPage.selectSet("Crypto Effectors");
    await workbenchSidebarPage.selectSet("COWP Subset");

    // Wait for compose bar to appear
    await expect(page.getByRole("button", { name: /minus/i })).toBeVisible({
      timeout: 10_000,
    });

    // Select minus, verify preview count, then create
    await page.getByRole("button", { name: /minus/i }).click();
    await workbenchSidebarPage.expectComposeResultCount(minusCount);

    // Create the derived set
    const createBtn = page.getByRole("button", { name: /create/i });
    await expect(createBtn).toBeEnabled();
    await createBtn.click();
    await workbenchSidebarPage.expectSetCount(3);

    // API verification of derived set
    const updatedResp = await apiClient.get("/api/v1/gene-sets?siteId=cryptodb");
    const updatedSets = await updatedResp.json();
    expect(updatedSets.length).toBe(3);
    const derived = updatedSets.find(
      (gs: { source: string }) => gs.source === "derived",
    );
    expect(derived).toBeDefined();
    expect(derived.geneCount).toBe(minusCount);
  });
});
