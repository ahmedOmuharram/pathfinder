import { test, expect } from "../fixtures/test";
import { clearAllGeneSets } from "../fixtures/api-client";

const BASE_URL = process.env["PLAYWRIGHT_BASE_URL"] ?? "http://localhost:3000";

test.describe("Chat → Workbench Flow", () => {
  test("build strategy via chat, navigate to workbench, add genes, run enrichment", async ({
    chatPage,
    graphPage,
    page,
    seedData,
    apiClient,
    sitePicker,
    workbenchSidebarPage,
    workbenchMainPage,
  }) => {
    await clearAllGeneSets(page.context(), BASE_URL);

    // ── Phase 1: Chat & Strategy ────────────────────────────────
    await chatPage.goto();
    await sitePicker.selectSite("plasmodb");
    await chatPage.newChat();

    // Chat with the AI
    await chatPage.send("find drug resistance genes in Plasmodium falciparum");
    await chatPage.expectAssistantMessage(/\[mock\]/);
    await chatPage.expectIdle();

    // Trigger planning artifact
    await chatPage.send("artifact graph");
    await chatPage.expectPlanningArtifact();

    // UI: Apply strategy
    await page.getByRole("button", { name: /apply to strategy/i }).click();
    await graphPage.expectCompactView();
    await chatPage.expectIdle();

    // UI: Step pills visible
    const pillCount = await graphPage.stepPills.count();
    expect(pillCount).toBeGreaterThan(0);

    // API: Strategy persisted — use captured ID for isolation
    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();

    // ── Phase 2: Workbench — Gene Sets ──────────────────────────
    await workbenchSidebarPage.goto();

    // Add gene set with real PlasmoDB genes
    const genes = seedData.plasmoGenes;
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Resistance Markers");
    await page.getByLabel(/gene ids/i).fill(genes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 10_000 });

    // UI: Gene count on card
    await workbenchSidebarPage.expectSetGeneCount("Resistance Markers", genes.length);

    // ── Phase 3: Activate & Enrichment ──────────────────────────
    await workbenchSidebarPage.activateSet("Resistance Markers");
    await workbenchMainPage.expectActiveSetHeader("Resistance Markers", genes.length);

    // UI: Run real enrichment
    await workbenchMainPage.runEnrichmentAndVerifyResults();
    await workbenchMainPage.expectEnrichmentResultsWithData();

    // API: Gene set persisted correctly (find by name — other workers may add sets)
    const setsResp = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    expect(setsResp.ok()).toBeTruthy();
    const sets = await setsResp.json();
    const ourSet = sets.find(
      (gs: { name: string }) => gs.name === "Resistance Markers",
    );
    expect(ourSet).toBeDefined();
    expect(ourSet.geneCount).toBe(genes.length);
  });
});
