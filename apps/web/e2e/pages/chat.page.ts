import { type Locator, type Page, expect } from "@playwright/test";

export class ChatPage {
  readonly composer: Locator;
  readonly messageInput: Locator;
  readonly sendButton: Locator;
  readonly stopButton: Locator;
  readonly newChatButton: Locator;
  readonly refreshConversationsButton: Locator;
  readonly planPanelHeading: Locator;
  readonly approvePlanButton: Locator;
  readonly phaseTimingBlock: Locator;

  constructor(private page: Page) {
    this.composer = page.getByTestId("message-composer");
    this.messageInput = page.getByTestId("message-input");
    this.sendButton = page.getByTestId("send-button");
    this.stopButton = page.getByTestId("stop-button");
    this.newChatButton = page.getByRole("button", { name: "New Chat" });
    this.refreshConversationsButton = page.getByTestId("conversations-refresh-button");
    this.planPanelHeading = page.getByRole("heading", { name: "Strategy Plan" });
    this.approvePlanButton = page.getByRole("button", { name: "Approve & Execute" });
    this.phaseTimingBlock = page.getByTestId("plan-phase-timing");
  }

  async goto() {
    await this.page.goto("/");
    await expect(this.composer).toBeVisible();
  }

  /** The strategy ID created by the last `newChat()` call. */
  lastStrategyId: string | null = null;

  /** Start a fresh conversation so the test is isolated from prior state. */
  async newChat() {
    const baseUrl = new URL(this.page.url()).origin;
    const selectedSite = await this.page
      .getByTestId("site-select")
      .inputValue()
      .catch(() => "veupathdb");

    const strategyCreated = await this.page.context().request.post(
      `${baseUrl}/api/v1/conversations/open`,
      {
        data: { siteId: selectedSite !== "" ? selectedSite : "veupathdb" },
        headers: { "X-Requested-With": "XMLHttpRequest" },
      },
    );

    if (!strategyCreated.ok()) {
      const failureBody = await strategyCreated.text().catch(() => "");
      throw new Error(
        `openStrategy failed: ${strategyCreated.status()} ${failureBody}`.trim(),
      );
    }

    const body = (await strategyCreated.json()) as {
      strategyId?: string;
      id?: string;
    };
    const strategyId = body.strategyId ?? body.id ?? null;
    if (strategyId == null || strategyId === "") {
      throw new Error("openStrategy returned no strategyId");
    }
    this.lastStrategyId = strategyId;

    await this.refreshConversationsButton.click();
    const conversationItem = this.page.locator(
      `[data-conversation-id="${strategyId}"]`,
    ).first();
    await expect(conversationItem).toBeVisible({ timeout: 10_000 });
    await conversationItem.click();

    await expect(this.composer).toBeVisible({ timeout: 10_000 });
    await expect(this.userMessages).toHaveCount(0, { timeout: 10_000 });
    await expect(this.assistantMessages).toHaveCount(0, { timeout: 10_000 });
  }

  async send(message: string) {
    // Retry fill if a background re-render (e.g. conversation fetch completing)
    // remounts the textarea and clears the text before we can click send.
    await expect(async () => {
      await this.messageInput.fill(message);
      await expect(this.sendButton).toBeEnabled();
    }).toPass({ timeout: 10_000 });
    await this.sendButton.click();
  }

  async stopStreaming() {
    await this.stopButton.click();
  }

  async approvePlan() {
    await this.approvePlanButton.click();
  }

  /** Get all assistant message bubbles. */
  get assistantMessages(): Locator {
    return this.page.getByTestId("assistant-message");
  }

  /** Get the nth assistant message (0-indexed). */
  assistantMessage(index: number): Locator {
    return this.assistantMessages.nth(index);
  }

  /** Get all user message bubbles. */
  get userMessages(): Locator {
    return this.page.getByTestId("user-message");
  }

  // ── Assertions ──────────────────────────────────────────────────

  async expectIdle(timeout = 60_000) {
    await expect(this.sendButton).toBeVisible({ timeout });
    await expect(this.stopButton).not.toBeVisible();
  }

  async expectStreaming() {
    await expect(this.stopButton).toBeVisible({ timeout: 10_000 });
  }

  /**
   * Assert that an assistant message matching `pattern` is visible.
   *
   * By default this finds ANY assistant message containing the pattern
   * (resilient to stale messages from prior conversations). Pass an
   * explicit `index` to pin to a specific position.
   */
  async expectAssistantMessage(
    pattern: RegExp,
    options?: { index?: number; timeout?: number },
  ) {
    const timeout = options?.timeout ?? 30_000;
    if (options?.index !== undefined) {
      await expect(this.assistantMessage(options.index)).toContainText(pattern, {
        timeout,
      });
    } else {
      // Find any assistant message matching the pattern.
      const matching = this.assistantMessages.filter({ hasText: pattern });
      await expect(matching.first()).toBeVisible({ timeout });
    }
  }

  async expectAssistantMessageCount(count: number) {
    await expect(this.assistantMessages).toHaveCount(count);
  }

  async expectDelegationDraft() {
    await expect(this.page.getByTestId("delegation-draft-details")).toBeVisible({
      timeout: 30_000,
    });
  }

  async expectPlanningArtifact() {
    await this.expectPlanPanel();
    await expect(this.page.getByText("presented", { exact: true })).toBeVisible({
      timeout: 60_000,
    });
  }

  async expectPlanPanel() {
    await expect(this.planPanelHeading).toBeVisible({ timeout: 60_000 });
    await expect(this.approvePlanButton).toBeVisible({ timeout: 60_000 });
  }

  async expectPhaseTiming(
    phase: "scoping" | "discovery" | "planning" | "execution" | "verification",
    status?: string | RegExp,
  ) {
    const row = this.page.getByTestId(`plan-phase-timing-${phase}`);
    await expect(row).toBeVisible({ timeout: 60_000 });
    if (status !== undefined) {
      await expect(this.page.getByTestId(`plan-phase-status-${phase}`)).toHaveText(status, {
        timeout: 60_000,
      });
    }
  }

  async expectCompactStrategyView() {
    // Compact strategy view renders step pills inside a border-t container.
    // Matches either real step names (e.g. "All ... genes") or mock labels.
    await expect(
      this.page
        .locator("[data-testid='compact-strategy-view'], [data-testid='step-pill']")
        .first(),
    ).toBeVisible({ timeout: 30_000 });
  }

  async expectSendDisabled() {
    await expect(this.sendButton).toBeDisabled();
  }

  async expectConversationTitleUpdated(pattern: RegExp) {
    await expect(this.page.getByTestId("conversation-item").first()).toContainText(
      pattern,
      { timeout: 15_000 },
    );
  }
}
