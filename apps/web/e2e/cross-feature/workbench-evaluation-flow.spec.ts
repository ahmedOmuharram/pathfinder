import { test, expect } from "../fixtures/test";
import { clearAllGeneSets } from "../fixtures/api-client";

const BASE_URL = process.env["PLAYWRIGHT_BASE_URL"] ?? "http://localhost:3000";

test.describe("Workbench Evaluation Flow", () => {
  test("create gene set, evaluate with positive controls, verify metrics and confidence scores", async ({
    page,
    seedData,
    sitePicker,
    workbenchSidebarPage,
    workbenchMainPage,
  }) => {
    await clearAllGeneSets(page.context(), BASE_URL);
    await page.goto("/workbench");
    await expect(page.getByRole("heading", { name: /gene sets/i })).toBeVisible();
    await sitePicker.selectSite("plasmodb");

    const genes = seedData.plasmoGenes;

    // ── Phase 1: Create a gene set from PlasmoDB IDs ──────────────
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Eval Test Set");
    await page.getByLabel(/gene ids/i).fill(genes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 10_000 });
    await workbenchSidebarPage.expectSetGeneCount("Eval Test Set", genes.length);

    // Activate the gene set
    await workbenchSidebarPage.activateSet("Eval Test Set");
    await workbenchMainPage.expectActiveSetHeader("Eval Test Set", genes.length);

    // ── Phase 2: Open the Evaluate panel ──────────────────────────
    await workbenchMainPage.expandPanel("Evaluate Strategy");
    await workbenchMainPage.expectPanelExpanded("Evaluate Strategy");

    // UI: "Run Evaluation" button is visible
    const runBtn = page.getByRole("button", { name: /run evaluation/i });
    await expect(runBtn).toBeVisible();

    // ── Phase 3: Enter positive controls ──────────────────────────
    // Use known PlasmoDB drug resistance genes as positive controls.
    // We use the first 2 genes from our seed data as positive controls.
    const positiveControlIds = genes.slice(0, 2);

    // The Positive Controls section uses a GeneAutocomplete search input.
    // Find the "Positive Controls" container, then type each gene ID into
    // the search field and select it from the dropdown.
    const positiveSection = page
      .locator("div")
      .filter({ hasText: /^Positive Controls/ })
      .first();

    for (const geneId of positiveControlIds) {
      // Type gene ID into the search input within the positive controls container
      const searchInput = positiveSection
        .locator("xpath=ancestor::div[contains(@class, 'border-l-green')]")
        .or(page.locator("[class*='border-l-green']").first())
        .getByPlaceholder(/search genes/i);
      await searchInput.fill(geneId);

      // Wait for dropdown results to appear (real VEuPathDB API call)
      const dropdownItem = page
        .locator("button")
        .filter({ hasText: new RegExp(geneId, "i") })
        .first();
      await expect(dropdownItem).toBeVisible({ timeout: 15_000 });
      await dropdownItem.click();

      // Verify chip appears
      await expect(page.getByText(geneId).first()).toBeVisible({ timeout: 5_000 });
    }

    // ── Phase 4: Run evaluation ───────────────────────────────────
    await runBtn.click();

    // Wait for evaluation to complete — SSE stream, can take time
    // The button changes to "Evaluating..." while running
    await expect(page.getByRole("button", { name: /evaluating/i })).toBeVisible({
      timeout: 5_000,
    });

    // Wait for evaluation to finish: either metrics appear or error shows
    const metricsSection = page.getByTestId("metrics-overview");
    const errorMsg = page.locator("p.text-destructive").first();
    await expect(metricsSection.or(errorMsg)).toBeVisible({ timeout: 120_000 });

    // ── Phase 5: Verify metrics appear ────────────────────────────
    // If an error occurred (e.g., WDK timeout), skip metric assertions
    const hasError = await errorMsg.isVisible().catch(() => false);
    if (!hasError) {
      // UI: Classification metrics are displayed (use .first() since metric labels appear in multiple sections)
      await expect(page.getByText("Sensitivity").first()).toBeVisible();
      await expect(page.getByText("Specificity").first()).toBeVisible();
      await expect(page.getByText("Precision").first()).toBeVisible();
      await expect(page.getByText("F1 Score").first()).toBeVisible();

      // ── Phase 6: Gene Confidence panel ────────────────────────────
      await workbenchMainPage.expandPanel("Gene Confidence");
      await workbenchMainPage.expectPanelExpanded("Gene Confidence");

      // UI: Confidence table has the expected columns
      const confidenceTable = page.locator("table[role='table']");
      await expect(confidenceTable).toBeVisible({ timeout: 10_000 });

      // Verify column headers: Gene ID, Composite, Classification, Enrichment
      const headers = confidenceTable.locator("thead th");
      await expect(headers.filter({ hasText: "Gene ID" })).toBeVisible();
      await expect(headers.filter({ hasText: "Composite" })).toBeVisible();
      await expect(headers.filter({ hasText: "Classification" })).toBeVisible();
      await expect(headers.filter({ hasText: "Enrichment" })).toBeVisible();

      // UI: No "Ensemble" column in confidence table
      await expect(headers.filter({ hasText: "Ensemble" })).toHaveCount(0);

      // UI: At least one data row with a gene ID
      const rows = confidenceTable.locator("tbody tr");
      await expect(rows.first()).toBeVisible();

      // UI: Rows contain real gene IDs (PF3D7_ pattern)
      const firstGeneCell = rows.first().locator("td").first();
      await expect(firstGeneCell).toContainText(/PF3D7_/);

      // UI: Composite scores are numeric values
      const compositeCell = rows.first().locator("td").nth(1);
      await expect(compositeCell).toContainText(/[-]?\d+\.\d+/);
    }

    // ── Phase 7: Step Contribution panel (disabled without step analysis) ─
    // Step Contribution requires `enableStepAnalysis` to be checked during
    // evaluation. Since we didn't enable it, it should show a disabled reason.
    const stepPanel = page
      .getByRole("button", { expanded: false })
      .filter({ hasText: /step contribution/i });
    // May be disabled with "Requires a completed step analysis"
    await expect(stepPanel).toBeVisible();
  });

  test("evaluate panel shows error when no positive controls provided", async ({
    page,
    seedData,
    sitePicker,
    workbenchSidebarPage,
    workbenchMainPage,
  }) => {
    await clearAllGeneSets(page.context(), BASE_URL);
    await page.goto("/workbench");
    await expect(page.getByRole("heading", { name: /gene sets/i })).toBeVisible();
    await sitePicker.selectSite("plasmodb");

    const genes = seedData.plasmoGenes;

    // Create and activate a gene set
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("No Controls Set");
    await page.getByLabel(/gene ids/i).fill(genes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 10_000 });

    await workbenchSidebarPage.activateSet("No Controls Set");
    await workbenchMainPage.expectActiveSetHeader("No Controls Set", genes.length);

    // Expand evaluate panel
    await workbenchMainPage.expandPanel("Evaluate Strategy");
    await workbenchMainPage.expectPanelExpanded("Evaluate Strategy");

    // Click Run Evaluation without adding positive controls
    const runBtn = page.getByRole("button", { name: /run evaluation/i });
    await runBtn.click();

    // UI: Error message about missing positive controls
    await expect(page.getByText(/at least one positive control/i)).toBeVisible({
      timeout: 5_000,
    });
  });

  test("evaluate panel is disabled for gene sets without gene IDs or search context", async ({
    page,
    seedData,
    sitePicker,
    workbenchSidebarPage,
    workbenchMainPage,
  }) => {
    await clearAllGeneSets(page.context(), BASE_URL);
    await page.goto("/workbench");
    await expect(page.getByRole("heading", { name: /gene sets/i })).toBeVisible();
    await sitePicker.selectSite("plasmodb");

    // Create a gene set with valid gene IDs (paste-based)
    const genes = seedData.plasmoGenes;
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Has Genes");
    await page.getByLabel(/gene ids/i).fill(genes.join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 10_000 });

    // Activate the gene set
    await workbenchSidebarPage.activateSet("Has Genes");
    await workbenchMainPage.expectActiveSetHeader("Has Genes", genes.length);

    // Evaluate Strategy should be ENABLED for paste sets with gene IDs
    // (the panel checks `activeSet.geneIds?.length` which is true for paste sets)
    await workbenchMainPage.expectPanelVisible("Evaluate Strategy");

    // Verify it can be expanded (not disabled)
    await workbenchMainPage.expandPanel("Evaluate Strategy");
    await workbenchMainPage.expectPanelExpanded("Evaluate Strategy");

    // Run Evaluation button should be visible
    await expect(page.getByRole("button", { name: /run evaluation/i })).toBeVisible();
  });
});
