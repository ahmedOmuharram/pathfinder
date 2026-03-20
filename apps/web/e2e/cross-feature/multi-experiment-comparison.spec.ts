import { test, expect } from "../fixtures/test";
import { clearAllGeneSets } from "../fixtures/api-client";

const BASE_URL = process.env["PLAYWRIGHT_BASE_URL"] ?? "http://localhost:3000";

test.describe("Multi-Experiment Comparison", () => {
  test("create multiple gene sets, run enrichment on each, compare via set operations", async ({
    page,
    seedData,
    sitePicker,
    workbenchSidebarPage,
    workbenchMainPage,
    apiClient,
  }) => {
    await clearAllGeneSets(page.context(), BASE_URL);
    await page.goto("/workbench");
    await expect(page.getByRole("heading", { name: /gene sets/i })).toBeVisible();
    await sitePicker.selectSite("plasmodb");

    const fullGenes = seedData.plasmoGenes;
    const subsetGenes = seedData.plasmoGenes.slice(0, 3);
    const fullCount = fullGenes.length;
    const subsetCount = subsetGenes.length;

    // ── Phase 1: Add two gene sets ──────────────────────────────
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Resistance Markers");
    await page.getByLabel(/gene ids/i).fill(fullGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 10_000 });
    await workbenchSidebarPage.expectSetGeneCount("Resistance Markers", fullCount);

    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Top Markers");
    await page.getByLabel(/gene ids/i).fill(subsetGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 10_000 });
    await workbenchSidebarPage.expectSetGeneCount("Top Markers", subsetCount);

    // ── Phase 2: Activate full set & run enrichment ─────────────
    await workbenchSidebarPage.activateSet("Resistance Markers");
    await workbenchMainPage.expectActiveSetHeader("Resistance Markers", fullCount);

    // UI: Run enrichment — real WDK enrichment API
    await workbenchMainPage.runEnrichmentAndVerifyResults();
    await workbenchMainPage.expectEnrichmentResultsWithData();
    await workbenchMainPage.expectEnrichmentTypeTabs();

    // ── Phase 3: Set operation with preview count verification ───
    await workbenchSidebarPage.selectSet("Resistance Markers");
    await workbenchSidebarPage.selectSet("Top Markers");

    await expect(page.getByRole("button", { name: /intersect/i })).toBeVisible({
      timeout: 10_000,
    });

    // UI: Preview shows intersection count = subsetCount (subset is contained in full)
    await workbenchSidebarPage.expectComposeResultCount(subsetCount);

    // Create derived set
    await workbenchSidebarPage.performOperation("intersect");
    await workbenchSidebarPage.expectSetCount(3);

    // API: Sets persisted with correct counts (find by name — other workers may add sets)
    const resp = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    expect(resp.ok()).toBeTruthy();
    const sets = await resp.json();
    expect(sets.length).toBeGreaterThanOrEqual(3);

    const fullSet = sets.find(
      (gs: { name: string }) => gs.name === "Resistance Markers",
    );
    expect(fullSet).toBeDefined();
    expect(fullSet.geneCount).toBe(fullCount);

    const derived = sets.find((gs: { source: string }) => gs.source === "derived");
    expect(derived).toBeDefined();
    expect(derived.geneCount).toBe(subsetCount);
    expect(derived.operation).toBe("intersect");
  });
});
