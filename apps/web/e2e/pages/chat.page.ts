import { type Locator, type Page, expect } from "@playwright/test";

export class ChatPage {
  readonly composer: Locator;
  readonly messageInput: Locator;
  readonly sendButton: Locator;
  readonly stopButton: Locator;
  readonly newChatButton: Locator;
  readonly refreshConversationsButton: Locator;
  readonly planArtifact: Locator;
  readonly decisionPresented: Locator;
  readonly approvePlanButton: Locator;
  /** Legacy alias retained so tests that reference `phaseTimingBlock` still type-check. */
  readonly phaseTimingBlock: Locator;

  constructor(private page: Page) {
    this.composer = page.getByTestId("message-composer");
    this.messageInput = page.getByTestId("message-input");
    this.sendButton = page.getByTestId("send-button");
    this.stopButton = page.getByTestId("stop-button");
    this.newChatButton = page.getByRole("button", { name: "New chat" });
    this.refreshConversationsButton = page.getByTestId("conversations-refresh-button");
    // Post-overhaul: planning emits a `data-plan-artifact` part inline in the
    // assistant message stream; approval is a `data-decision-presented` part
    // with option buttons (label "approve" continues to execution).
    this.planArtifact = page.getByTestId("data-plan-artifact");
    this.decisionPresented = page.getByTestId("data-decision-presented");
    this.approvePlanButton = this.decisionPresented.getByRole("button", {
      name: /approve/i,
    });
    // Phase-timing block was removed in the overhaul; the locator remains as
    // a never-matching stub so legacy specs continue to type-check.
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
    // The site picker testid was removed in the chat overhaul; default to
    // veupathdb (portal site) which all tests use.
    const selectedSite = "veupathdb";

    const strategyCreated = await this.page.context().request.post(
      `${baseUrl}/api/v1/conversations/open`,
      {
        data: { siteId: selectedSite },
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
      conversationId?: string;
      strategyId?: string;
      id?: string;
    };
    const strategyId =
      body.conversationId ?? body.strategyId ?? body.id ?? null;
    if (strategyId == null || strategyId === "") {
      throw new Error("openStrategy returned no conversationId");
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
    // Post-overhaul: there's no explicit stop button on the composer; idle
    // is signified by the Send button being enabled.
    await expect(this.sendButton).toBeVisible({ timeout });
    await expect(this.sendButton).toBeEnabled({ timeout });
  }

  async expectStreaming() {
    // While streaming the Send button is disabled.
    await expect(this.sendButton).toBeDisabled({ timeout: 10_000 });
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
    await expect(this.planArtifact).toBeVisible({ timeout: 60_000 });
    await expect(this.approvePlanButton).toBeVisible({ timeout: 60_000 });
  }

  /**
   * Backwards-compatible alias for tests that haven't been migrated to the
   * new plan artifact API yet.
   */
  async expectPlanPanel() {
    await this.expectPlanningArtifact();
  }

  /** Stub kept for legacy tests; phase-timing UI was removed in the overhaul. */
  async expectPhaseTiming(
    _phase: "scoping" | "discovery" | "planning" | "execution" | "verification",
    _status?: string | RegExp,
  ) {
    // No-op: phase-timing block was deleted.
  }

  /** Compatibility alias for the rail-based step list (replaces compact view). */
  async expectCompactStrategyView() {
    await expect(this.page.getByTestId("compact-strategy-view")).toBeVisible({
      timeout: 30_000,
    });
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
