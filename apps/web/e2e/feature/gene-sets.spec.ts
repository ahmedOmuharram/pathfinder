import { test, expect } from "../fixtures/test";
import { clearAllGeneSets } from "../fixtures/api-client";

const BASE_URL = process.env["PLAYWRIGHT_BASE_URL"] ?? "http://localhost:3000";

test.describe("Gene Sets", () => {
  test.beforeEach(async ({ page, sitePicker }) => {
    await clearAllGeneSets(page.context(), BASE_URL);
    await page.goto("/workbench");
    await expect(page.getByRole("heading", { name: /gene sets/i })).toBeVisible();
    await sitePicker.selectSite("plasmodb");
  });

  test("add gene set shows correct count in UI and persists to DB", async ({
    page,
    seedData,
    workbenchSidebarPage,
    apiClient,
  }) => {
    const genes = seedData.plasmoGenes;

    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Drug Resistance Markers");
    await page.getByLabel(/gene ids/i).fill(genes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 10_000 });

    // UI: Gene count displayed on card
    await workbenchSidebarPage.expectSetCount(1);
    await workbenchSidebarPage.expectSetGeneCount(
      "Drug Resistance Markers",
      genes.length,
    );

    // API: Gene set persisted with correct gene IDs (find by name — other workers may add sets)
    const resp = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    expect(resp.ok()).toBeTruthy();
    const sets = await resp.json();
    const ourSet = sets.find(
      (gs: { name: string }) => gs.name === "Drug Resistance Markers",
    );
    expect(ourSet).toBeDefined();
    expect(ourSet.geneCount).toBe(genes.length);
    expect(ourSet.geneIds).toHaveLength(genes.length);
  });

  test("activate gene set shows header with count and analysis panels", async ({
    page,
    seedData,
    workbenchSidebarPage,
    workbenchMainPage,
  }) => {
    const genes = seedData.plasmoGenes;

    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Test Set");
    await page.getByLabel(/gene ids/i).fill(genes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 10_000 });

    // UI: Activate and verify header shows name + gene count
    await workbenchSidebarPage.activateSet("Test Set");
    await workbenchMainPage.expectActiveSetHeader("Test Set", genes.length);

    // UI: Analysis panels appear
    await workbenchMainPage.expectPanelVisible("Enrichment Analysis");
    await workbenchMainPage.expectPanelVisible("Results Table");
  });

  test("set operations show preview count and create derived set in DB", async ({
    page,
    seedData,
    workbenchSidebarPage,
    apiClient,
  }) => {
    const fullGenes = seedData.plasmoGenes;
    const subsetGenes = seedData.plasmoGenes.slice(0, 3);
    const intersectionCount = subsetGenes.length; // subset is contained in full

    // Add full set
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Full Set");
    await page.getByLabel(/gene ids/i).fill(fullGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 10_000 });
    await workbenchSidebarPage.expectSetGeneCount("Full Set", fullGenes.length);

    // Add subset
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Subset");
    await page.getByLabel(/gene ids/i).fill(subsetGenes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 10_000 });
    await workbenchSidebarPage.expectSetGeneCount("Subset", subsetGenes.length);

    // Select both sets
    await workbenchSidebarPage.selectSet("Full Set");
    await workbenchSidebarPage.selectSet("Subset");

    // UI: Compose bar shows operations
    await expect(page.getByRole("button", { name: /intersect/i })).toBeVisible({
      timeout: 10_000,
    });

    // UI: Preview count shows intersection count
    await workbenchSidebarPage.expectComposeResultCount(intersectionCount);

    // UI: Perform intersection
    await workbenchSidebarPage.performOperation("intersect");
    await workbenchSidebarPage.expectSetCount(3);

    // API: Derived set persisted with correct count (find by source — other workers may add sets)
    const resp = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    const sets = await resp.json();
    expect(sets.length).toBeGreaterThanOrEqual(3);
    const derived = sets.find((gs: { source: string }) => gs.source === "derived");
    expect(derived).toBeDefined();
    expect(derived.geneCount).toBe(intersectionCount);
    expect(derived.operation).toBe("intersect");
  });

  test("filter gene sets by name", async ({ page, seedData, workbenchSidebarPage }) => {
    const geneIds = seedData.plasmoGenes.slice(0, 2).join("\n");
    for (let i = 0; i < 5; i++) {
      await workbenchSidebarPage.openAddModal();
      await page.getByLabel(/name/i).fill(`Filter Test ${i}`);
      await page.getByLabel(/gene ids/i).fill(geneIds);
      await page.getByRole("button", { name: /add gene set/i }).click();
      await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 10_000 });
    }

    // UI: Filter input visible at 5+ sets
    await workbenchSidebarPage.filterSets("Filter Test 3");
    await workbenchSidebarPage.expectSetCount(1);
  });
});
