import { type Locator, type Page, expect } from "@playwright/test";

export class SidebarPage {
  readonly refreshButton: Locator;
  readonly newButton: Locator;
  readonly searchInput: Locator;

  constructor(private page: Page) {
    this.refreshButton = page.getByTestId("conversations-refresh-button");
    this.newButton = page.getByTestId("conversations-new-button");
    this.searchInput = page.getByTestId("conversations-search-input");
  }

  /** All conversation items in the sidebar. */
  get items(): Locator {
    return this.page.getByTestId("conversation-item");
  }

  /** A specific conversation by its data-conversation-id attribute. */
  item(conversationId: string): Locator {
    return this.page.locator(
      `[data-testid="conversation-item"][data-conversation-id="${conversationId}"]`,
    );
  }

  async createNew() {
    await this.newButton.click();
  }

  async search(query: string) {
    await this.searchInput.fill(query);
  }

  async clearSearch() {
    await this.searchInput.clear();
  }

  async selectConversation(conversationId: string) {
    await this.item(conversationId).click();
  }

  /** Open the dropdown menu on a conversation item via the "..." button. */
  private async openMenu(conversationId: string) {
    // Hover to reveal the overflow menu button, then click it
    await this.item(conversationId).hover();
    await this.item(conversationId)
      .getByRole("button", { name: /conversation actions/i })
      .click();
  }

  async rename(conversationId: string, newName: string) {
    await this.openMenu(conversationId);
    await this.page.getByRole("menuitem", { name: /rename/i }).click();
    const renameInput = this.page.getByTestId("conversation-rename-input");
    await renameInput.clear();
    await renameInput.fill(newName);
    await renameInput.press("Enter");
  }

  async delete(conversationId: string) {
    await this.openMenu(conversationId);
    await this.page.getByRole("menuitem", { name: /delete/i }).click();
    // Confirm in the delete modal
    await this.page
      .getByRole("dialog")
      .getByRole("button", { name: /delete/i })
      .click();
  }

  async duplicate(conversationId: string) {
    await this.openMenu(conversationId);
    await this.page.getByRole("menuitem", { name: /duplicate/i }).click();
  }

  async refresh() {
    await this.refreshButton.click();
  }

  async expectConversationCount(count: number) {
    await expect(this.items).toHaveCount(count);
  }

  async expectConversationVisible(conversationId: string) {
    await expect(this.item(conversationId)).toBeVisible();
  }

  async expectConversationName(conversationId: string, name: string | RegExp) {
    const pattern = typeof name === "string" ? new RegExp(name) : name;
    await expect(this.item(conversationId)).toContainText(pattern);
  }

  /** Get the first conversation item's data-conversation-id. */
  async firstConversationId(): Promise<string> {
    const first = this.items.first();
    await expect(first).toBeVisible({ timeout: 15_000 });
    return (await first.getAttribute("data-conversation-id")) ?? "";
  }

  // ── Dismissed section ──────────────────────────────────────────

  /** The "Dismissed (N)" toggle button. */
  get dismissedToggle(): Locator {
    return this.page.getByTestId("dismissed-toggle");
  }

  /** All dismissed items inside the expanded dismissed section. */
  get dismissedItems(): Locator {
    return this.page.getByTestId("dismissed-item");
  }

  /** A specific dismissed item by its data-conversation-id attribute. */
  dismissedItem(conversationId: string): Locator {
    return this.page.locator(
      `[data-testid="dismissed-item"][data-conversation-id="${conversationId}"]`,
    );
  }

  /** Expand the dismissed section (idempotent — no-op if already expanded). */
  async expandDismissed() {
    await expect(this.dismissedToggle).toBeVisible({ timeout: 15_000 });
    // Only click if items are not already visible (prevents toggling off).
    const alreadyExpanded = await this.dismissedItems.first().isVisible();
    if (!alreadyExpanded) {
      await this.dismissedToggle.click();
    }
    await expect(this.dismissedItems.first()).toBeVisible({ timeout: 5_000 });
  }

  /** Collapse the dismissed section (idempotent — no-op if already collapsed). */
  async collapseDismissed() {
    const isExpanded = await this.dismissedItems.first().isVisible();
    if (isExpanded) {
      await this.dismissedToggle.click();
    }
  }

  /** Click the Restore button on a specific dismissed item. */
  async restoreDismissed(conversationId: string) {
    const item = this.dismissedItem(conversationId);
    await expect(item).toBeVisible({ timeout: 10_000 });
    await item.getByTestId("dismissed-restore-button").click();
  }

  /** Assert the dismissed toggle shows the expected count. */
  async expectDismissedCount(count: number) {
    await expect(this.dismissedToggle).toContainText(`Dismissed (${count})`, {
      timeout: 15_000,
    });
  }

  /** Assert the dismissed toggle is not visible (no dismissed items). */
  async expectNoDismissedSection() {
    await expect(this.dismissedToggle).not.toBeVisible({ timeout: 10_000 });
  }

  /** Assert a dismissed item is visible (section must be expanded). */
  async expectDismissedItemVisible(conversationId: string) {
    await expect(this.dismissedItem(conversationId)).toBeVisible({
      timeout: 10_000,
    });
  }
}
