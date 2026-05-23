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
  readonly denyPlanButton: Locator;

  constructor(private page: Page) {
    this.composer = page.getByTestId("message-composer");
    this.messageInput = page.getByTestId("message-input");
    this.sendButton = page.getByTestId("send-button");
    this.stopButton = page.getByTestId("stop-button");
    this.newChatButton = page.getByRole("button", { name: "New chat" });
    this.refreshConversationsButton = page.getByTestId("conversations-refresh-button");
    this.planArtifact = page.getByTestId("data-plan-artifact");
    this.decisionPresented = page.getByTestId("data-decision-presented");
    this.approvePlanButton = page.getByTestId("plan-approve");
    this.denyPlanButton = page.getByTestId("plan-deny");
  }

  async goto() {
    await this.page.goto("/");
    await expect(this.composer).toBeVisible();
  }

  /** The strategy ID created by the last `newChat()` call. */
  lastStrategyId: string | null = null;

  /** Start a fresh conversation so the test is isolated from prior state. */
  async newChat(siteId: string = "veupathdb") {
    const baseUrl = new URL(this.page.url()).origin;
    const selectedSite = siteId;

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
    await expect(async () => {
      await this.messageInput.fill(message);
      await expect(this.sendButton).toBeEnabled();
      await this.sendButton.click({ trial: false, timeout: 2_000 });
    }).toPass({ timeout: 30_000 });
  }

  async stopStreaming() {
    await this.stopButton.click();
  }

  async openPlanRail() {
    const trigger = this.page
      .locator('[aria-label="Right rail"]')
      .getByRole("button", { name: /^(Open|Close) Plan$/ });
    await expect(trigger).toBeVisible({ timeout: 30_000 });
    if ((await trigger.getAttribute("aria-pressed")) !== "true") {
      await trigger.click();
      await expect(trigger).toHaveAttribute("aria-pressed", "true", { timeout: 5_000 });
    }
  }

  async approvePlan() {
    await this.openPlanRail();
    await expect(this.approvePlanButton).toBeVisible({ timeout: 60_000 });
    await this.approvePlanButton.click();
  }

  async denyPlan() {
    await this.openPlanRail();
    await expect(this.denyPlanButton).toBeVisible({ timeout: 60_000 });
    await this.denyPlanButton.click();
  }

  /** Last (most recent) plan artifact rendered inline in any assistant message. */
  get lastPlanArtifact(): Locator {
    return this.planArtifact.last();
  }

  get assistantMessages(): Locator {
    return this.page.locator(".is-assistant");
  }

  assistantMessage(index: number): Locator {
    return this.assistantMessages.nth(index);
  }

  get userMessages(): Locator {
    return this.page.locator(".is-user");
  }

  // ── Assertions ──────────────────────────────────────────────────

  async expectIdle(timeout = 60_000) {
    await expect(this.sendButton).toBeVisible({ timeout });
    await expect(this.messageInput).toBeEditable({ timeout });
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

  /** Text content of the most recently rendered assistant message. */
  async lastAssistantMessageText(): Promise<string> {
    return this.assistantMessages.evaluateAll((els) => {
      const last = els[els.length - 1];
      return last?.textContent ?? "";
    });
  }

  async expectDelegationDraft() {
    await expect(this.page.getByTestId("delegation-draft-details")).toBeVisible({
      timeout: 30_000,
    });
  }

  async expectPlanningArtifact() {
    await expect(this.planArtifact.first()).toBeVisible({ timeout: 60_000 });
    await this.openPlanRail();
    await expect(this.approvePlanButton).toBeVisible({ timeout: 60_000 });
  }

  /** Assert at least one user-blocking question (from a scoping AWAITING_USER outcome). */
  async expectClarifyingQuestions(pattern: RegExp = /clarify|which|what evidence|how strict/i) {
    await this.expectAssistantMessage(pattern, { timeout: 60_000 });
  }

  /** Assert the turn ended waiting on the user (composer idle, no streaming). */
  async expectAwaitingUser() {
    await this.expectIdle();
  }

  /** Assert a verification success digest is visible (typed by characteristic phrases). */
  async expectVerificationSuccess(
    pattern: RegExp = /verified end-to-end|verification passed|root size|candidate drug targets/i,
  ) {
    await this.expectAssistantMessage(pattern, { timeout: 90_000 });
  }

  /** Assert a verification failure digest is visible (any failed-leaf signal). */
  async expectVerificationFeedback(
    pattern: RegExp = /returned 0|root size is 0|too narrow|loosen/i,
  ) {
    await this.expectAssistantMessage(pattern, { timeout: 90_000 });
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
