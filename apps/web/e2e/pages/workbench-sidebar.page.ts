import { type Locator, type Page, expect } from "@playwright/test";

export class WorkbenchSidebarPage {
  readonly addButton: Locator;

  constructor(private page: Page) {
    this.addButton = page.getByRole("button", { name: /add/i });
  }

  /** Navigate to the workbench, preserving the currently-selected site so
   *  gene sets are created on the site the test already switched to. */
  async goto() {
    const currentSite = new URL(this.page.url()).pathname.split("/")[1];
    const path =
      currentSite != null && currentSite !== ""
        ? `/${currentSite}/workbench`
        : "/workbench";
    await this.page.goto(path);
    await expect(this.page.getByRole("heading", { name: /gene sets/i })).toBeVisible();
  }

  /** Click the "Add" button to open the Add Gene Set modal. */
  async openAddModal() {
    await this.addButton.click();
    await expect(this.page.getByRole("dialog")).toBeVisible();
  }

  /** Get the filter input (visible at 5+ sets). */
  get filterInput(): Locator {
    return this.page.getByPlaceholder(/filter/i);
  }

  async filterSets(query: string) {
    await this.filterInput.fill(query);
  }

  /** Get a gene set card by its name. */
  geneSetCard(name: string): Locator {
    return this.page.getByRole("button", { name }).locator("..");
  }

  /** Activate a gene set by clicking its name. */
  async activateSet(name: string) {
    await this.page.getByRole("button").filter({ hasText: name }).first().click();
  }

  /** Select a gene set checkbox. */
  async selectSet(name: string) {
    await this.page
      .getByRole("checkbox", { name: new RegExp(`select ${name}`, "i") })
      .check();
  }

  /** Deselect a gene set checkbox. */
  async deselectSet(name: string) {
    await this.page
      .getByRole("checkbox", { name: new RegExp(`select ${name}`, "i") })
      .uncheck();
  }

  /** Perform a compose bar set operation (union/intersect/minus).
   *  Selects the operation type, then clicks "Create" to execute. */
  async performOperation(operation: "union" | "intersect" | "minus") {
    await this.page.getByRole("button", { name: new RegExp(operation, "i") }).click();

    const createBtn = this.page.getByRole("button", { name: /create/i });
    await expect(createBtn).toBeEnabled();
    await createBtn.click();
  }

  // ── Assertions ─────────────────────────────────────────────────

  async expectSetCount(count: number) {
    const checkboxes = this.page.getByRole("checkbox", {
      name: /select/i,
    });
    await expect(checkboxes).toHaveCount(count);
  }

  async expectActiveSet(name: string) {
    await expect(
      this.page.locator(".bg-muted").filter({ hasText: name }),
    ).toBeVisible();
  }

  /** Verify a gene set card shows a specific gene count number. */
  async expectSetGeneCount(name: string, count: number) {
    const card = this.page.getByRole("button").filter({ hasText: name }).locator("..");
    await expect(card.getByText(count.toLocaleString(), { exact: true })).toBeVisible();
  }

  /** Verify the compose bar shows expected result count before creating. */
  async expectComposeResultCount(count: number) {
    await expect(
      this.page.getByText(new RegExp(`${count.toLocaleString()}\\s+gene`, "i")),
    ).toBeVisible({ timeout: 10_000 });
  }

  async expectEmptyState() {
    await expect(this.page.getByText(/no gene sets yet/i)).toBeVisible();
  }
}
