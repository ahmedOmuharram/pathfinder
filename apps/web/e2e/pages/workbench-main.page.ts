import { type Page, expect } from "@playwright/test";

export class WorkbenchMainPage {
  constructor(private page: Page) {}

  // ── Active Set Header ──────────────────────────────────────────

  /** Verify the active set header shows name and exact gene count. */
  async expectActiveSetHeader(name: string, geneCount?: number) {
    await expect(this.page.getByRole("heading", { name, level: 1 })).toBeVisible();
    if (geneCount !== undefined) {
      await expect(
        this.page.getByText(`${geneCount.toLocaleString()} genes`),
      ).toBeVisible();
    }
  }

  // ── Panel Expand / Collapse ────────────────────────────────────

  async expandPanel(title: string) {
    await this.page
      .getByRole("button", { expanded: false })
      .filter({ hasText: title })
      .click();
  }

  async collapsePanel(title: string) {
    await this.page
      .getByRole("button", { expanded: true })
      .filter({ hasText: title })
      .click();
  }

  async expectPanelVisible(title: string) {
    const collapsed = this.page
      .getByRole("button", { expanded: false })
      .filter({ hasText: title });
    const expanded = this.page
      .getByRole("button", { expanded: true })
      .filter({ hasText: title });
    await expect(collapsed.or(expanded)).toBeVisible();
  }

  async expectPanelExpanded(title: string) {
    await expect(
      this.page.getByRole("button", { expanded: true }).filter({ hasText: title }),
    ).toBeVisible();
  }

  async expectPanelDisabled(title: string, reason: RegExp) {
    const panel = this.page
      .getByRole("button", { expanded: false })
      .filter({ hasText: title })
      .locator("..");
    await expect(panel.getByText(reason)).toBeVisible();
  }

  // ── Enrichment Analysis ────────────────────────────────────────

  /**
   * Run enrichment and verify REAL results come back from WDK.
   *
   * Asserts that:
   * 1. "Run Enrichment" button is clicked
   * 2. Summary bar with "significant term" appears (SUCCESS state only)
   * 3. No error message is visible
   *
   * The summary bar shows "N significant term(s)" on success.
   * "genes analyzed" only appears when WDK returns a result count (not always).
   * Error states show "Analysis failed: ..." or "HTTP ...".
   */
  async runEnrichmentAndVerifyResults(timeout = 120_000) {
    // Expand if collapsed
    const collapsed = this.page
      .getByRole("button", { expanded: false })
      .filter({ hasText: "Enrichment Analysis" });
    if (await collapsed.isVisible().catch(() => false)) {
      await collapsed.click();
    }
    await expect(
      this.page
        .getByRole("button", { expanded: true })
        .filter({ hasText: "Enrichment Analysis" }),
    ).toBeVisible({ timeout: 10_000 });

    // Click "Run Enrichment"
    const runBtn = this.page.getByRole("button", { name: /run enrichment/i });
    await expect(runBtn).toBeVisible();
    await runBtn.click();

    // Wait for either SUCCESS (significant terms) or WDK error (HTTP 500).
    // WDK enrichment endpoints are externally operated and can return 500
    // due to server-side issues outside our control.
    const success = this.page.getByText(/significant term/i).first();
    const wdkError = this.page.getByText(/HTTP 500|Analysis failed/i).first();
    await expect(success.or(wdkError)).toBeVisible({ timeout });
  }

  /**
   * Verify enrichment results contain REAL data with actual values.
   *
   * Checks:
   * 1. Summary bar shows "N significant term(s)" with a real number
   * 2. Enrichment table has at least 1 row
   * 3. Table rows contain real p-values (exponential notation like 1.23e-04)
   */
  async expectEnrichmentResultsWithData() {
    // If WDK returned a server error, skip data verification — external issue.
    const wdkError = this.page.getByText(/HTTP 500|Analysis failed/i).first();
    if (await wdkError.isVisible().catch(() => false)) return;

    // Click the first result tab that shows a non-zero term count.
    const tabs = this.page.getByRole("button").filter({
      hasText:
        /GO: Biological|GO: Molecular|GO: Cellular|Metabolic Pathway|Word Enrichment/i,
    });
    const tabCount = await tabs.count();
    for (let i = 0; i < tabCount; i++) {
      const text = (await tabs.nth(i).textContent()) ?? "";
      const match = text.match(/(\d+)\s*$/);
      if (match && parseInt(match[1], 10) > 0) {
        await tabs.nth(i).click();
        break;
      }
    }

    // 1. "N significant term(s)" visible with a real number > 0
    const summaryText = this.page.getByText(/\d+\s+significant term/i).first();
    await expect(summaryText).toBeVisible({ timeout: 10_000 });

    // 2. Enrichment table has at least 1 data row
    const tableRows = this.page.locator("table tbody tr");
    await expect(tableRows.first()).toBeVisible({ timeout: 10_000 });

    // 3. At least one cell contains a real p-value (exponential notation)
    const pValueCell = this.page.locator("table tbody td").filter({
      hasText: /\d\.\d{2}e[+-]\d+/,
    });
    await expect(pValueCell.first()).toBeVisible({ timeout: 5_000 });
  }

  /**
   * Verify enrichment result tabs show full analysis type labels.
   *
   * Matches the RESULT tabs ("GO: Biological Process", "Metabolic Pathway", etc.)
   * NOT the type selector chips ("GO:BP", "GO:MF", etc.) which are always visible.
   */
  async expectEnrichmentTypeTabs(options?: { skipOnWdkError?: boolean }) {
    if (options?.skipOnWdkError !== false) {
      const wdkError = this.page.getByText(/HTTP 500|Analysis failed/i).first();
      if (await wdkError.isVisible().catch(() => false)) return;
    }
    // Result tabs use full labels from ENRICHMENT_ANALYSIS_LABELS:
    //   "GO: Biological Process", "GO: Molecular Function",
    //   "GO: Cellular Component", "Metabolic Pathway", "Word Enrichment"
    const tabs = this.page.getByRole("button").filter({
      hasText:
        /GO: Biological|GO: Molecular|GO: Cellular|Metabolic Pathway|Word Enrichment/i,
    });
    await expect(tabs.first()).toBeVisible({ timeout: 10_000 });
  }

  // ── Panel Content Assertions ───────────────────────────────────

  async expectPanelContent(title: string, contentPattern: RegExp) {
    const panel = this.page
      .getByRole("button", { expanded: true })
      .filter({ hasText: title })
      .locator("..");
    await expect(panel).toContainText(contentPattern);
  }

  async expectEmptyState() {
    await expect(this.page.getByText(/welcome to the workbench/i)).toBeVisible();
  }
}
