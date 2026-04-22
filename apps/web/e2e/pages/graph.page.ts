import { type Locator, type Page, expect } from "@playwright/test";

/**
 * Page object for the strategy graph + step editor surfaces.
 *
 * Targets the post-overhaul UI:
 * - Read-only rail panel on `/conversation/[id]` with an "Open" button
 * - Full-page editor at `/conversation/[id]/strategy` with a CanvasTopbar +
 *   CanvasControls + SelectionActionBar
 * - Right-anchored Sheet step editor (auto-saves; no Save button)
 * - Combine creation by drag → INTERSECT default → Sheet opens with venn picker
 */
export class GraphPage {
  constructor(private page: Page) {}

  // ── Rail panel (read-only step list on /conversation/[id]) ──────

  /** The vertical step list panel rendered in the right rail. */
  get railPanel(): Locator {
    return this.page.getByTestId("rail-strategy-panel");
  }

  /** The "Open" button in the rail header that navigates to /strategy. */
  get railOpenButton(): Locator {
    return this.page.getByTestId("rail-strategy-open");
  }

  /** All clickable step rows inside the compact view in the rail. */
  get railStepRows(): Locator {
    return this.page
      .getByTestId("compact-strategy-view")
      .locator("[data-testid^='compact-step-row-']");
  }

  /** A specific step row in the rail by step id. */
  railStepRow(stepId: string): Locator {
    return this.page.getByTestId(`compact-step-row-${stepId}`);
  }

  /** Footer row with "N steps". */
  get railFooter(): Locator {
    return this.page.getByTestId("rail-strategy-footer");
  }

  // ── Strategy page chrome (/conversation/[id]/strategy) ──────────

  /** The CanvasTopbar mounted on the /strategy route. */
  get strategyPageTopbar(): Locator {
    return this.page.getByTestId("canvas-topbar");
  }

  /** "Back to chat" button in the canvas topbar. */
  get strategyPageBackButton(): Locator {
    return this.page.getByTestId("canvas-topbar-back");
  }

  /** Step count text in the canvas topbar. */
  get strategyPageStepCount(): Locator {
    return this.page.getByTestId("canvas-topbar-step-count");
  }

  /** Sync state pill in the canvas topbar (idle/saving/error/paused). */
  get strategyPageSyncState(): Locator {
    return this.page.getByTestId("canvas-topbar-sync-state");
  }

  /** Inline-editable strategy name input in the canvas topbar. */
  get strategyPageNameInput(): Locator {
    return this.page.getByLabel("Strategy name");
  }

  /** Floating canvas controls (relayout/fit/zoom) bottom-right. */
  get canvasControls(): Locator {
    return this.page.getByTestId("canvas-controls");
  }

  /** Contextual selection action bar (top-right; visible when ≥1 node selected). */
  get selectionActionBar(): Locator {
    return this.page.getByTestId("selection-action-bar");
  }

  /** Validation alert banner shown when the strategy has record-type mismatches. */
  get validationAlert(): Locator {
    return this.page.getByTestId("validation-alert");
  }

  /** Empty-state CTA when no steps exist. */
  get emptyState(): Locator {
    return this.page.getByTestId("strategy-empty-state");
  }

  // ── Editor Sheet (right-anchored, opens on step click) ───────────

  /** The Sheet container (Radix Dialog) with the step editor inside. */
  get editorSheet(): Locator {
    return this.page.getByTestId("step-editor-sheet");
  }

  /** The default close button rendered by SheetContent. */
  get editorSheetClose(): Locator {
    return this.editorSheet.locator("[data-slot='sheet-close']");
  }

  /** Editor footer (sync status + result count + WDK link). */
  get editorFooter(): Locator {
    return this.page.getByTestId("step-editor-footer");
  }

  /** Editor sync state indicator (data-sync-state="idle|saving|error|paused"). */
  get editorSyncState(): Locator {
    return this.page.getByTestId("step-editor-sync-state");
  }

  /** Inline-editable step name input in the editor sheet header. */
  get editorStepNameInput(): Locator {
    return this.editorSheet.getByLabel("Step name");
  }

  // ── Venn picker (combine step editor body) ───────────────────────

  /** Venn picker root (visible when editing a combine step). */
  get vennPicker(): Locator {
    return this.page.getByTestId("venn-picker");
  }

  /**
   * One of the three clickable region paths inside the venn picker.
   * Maps user-visible operator regions to the underlying CombineOperator.
   */
  vennRegion(op: "MINUS" | "INTERSECT" | "RMINUS"): Locator {
    const ariaLabelByOp: Record<typeof op, string> = {
      MINUS: "A only",
      INTERSECT: "Intersection region",
      RMINUS: "B only",
    };
    return this.vennPicker.getByLabel(ariaLabelByOp[op]);
  }

  /** Operator readout text below the venn (shows current operator). */
  get vennReadout(): Locator {
    return this.vennPicker.locator("[data-slot='venn-readout']");
  }

  // ── Edge context menu ────────────────────────────────────────────

  /** Operator grid inside the edge context menu (Popover). */
  get edgeContextMenuOperatorGrid(): Locator {
    return this.page.getByTestId("edge-context-menu-operator-grid");
  }

  // ── ReactFlow nodes (canvas) ─────────────────────────────────────

  /** All strategy graph nodes in the ReactFlow canvas. */
  get nodes(): Locator {
    return this.page.locator("[data-testid^='rf-node-']");
  }

  node(stepId: string): Locator {
    return this.page.getByTestId(`rf-node-${stepId}`);
  }

  async clickNode(stepId: string) {
    await this.node(stepId).click();
  }

  async askAboutNode(stepId: string) {
    await this.node(stepId).hover();
    await this.page.getByTestId(`rf-add-to-chat-${stepId}`).click();
  }

  // ── Navigation helpers ──────────────────────────────────────────

  /** Navigate directly to the strategy editor route for a conversation. */
  async goToStrategy(siteId: string, conversationId: string) {
    await this.page.goto(`/${siteId}/conversation/${conversationId}/strategy`);
    await this.expectOnStrategyRoute(conversationId);
  }

  async expectOnStrategyRoute(conversationId: string) {
    await expect(this.page).toHaveURL(
      new RegExp(`/conversation/${conversationId}/strategy(?:/|$)`),
      { timeout: 10_000 },
    );
  }

  async expectOnChatRoute(conversationId: string) {
    await expect(this.page).toHaveURL(
      new RegExp(`/conversation/${conversationId}(?:\\?.*)?$`),
      { timeout: 10_000 },
    );
  }

  // ── Compound assertions ──────────────────────────────────────────

  /** Assert the rail panel with steps is visible (planning artifact applied). */
  async expectRailPanel() {
    await expect(this.railPanel).toBeVisible({ timeout: 30_000 });
  }

  async expectStrategyTopbar() {
    await expect(this.strategyPageTopbar).toBeVisible({ timeout: 15_000 });
  }

  async expectEditorSheetOpen() {
    await expect(this.editorSheet).toBeVisible({ timeout: 10_000 });
  }

  async expectEditorSheetClosed() {
    await expect(this.editorSheet).toBeHidden({ timeout: 10_000 });
  }

  async expectNodeCount(count: number) {
    await expect(this.nodes).toHaveCount(count, { timeout: 30_000 });
  }

  async expectNodeVisible(stepId: string) {
    await expect(this.node(stepId)).toBeVisible({ timeout: 10_000 });
  }
}
