import { type Locator, type Page, expect } from "@playwright/test";

export class ChatPage {
  readonly composer: Locator;
  readonly messageInput: Locator;
  readonly sendButton: Locator;
  readonly stopButton: Locator;
  readonly newChatButton: Locator;

  constructor(private page: Page) {
    this.composer = page.getByTestId("message-composer");
    this.messageInput = page.getByTestId("message-input");
    this.sendButton = page.getByTestId("send-button");
    this.stopButton = page.getByTestId("stop-button");
    this.newChatButton = page.getByRole("button", { name: "New Chat" });
  }

  async goto() {
    await this.page.goto("/");
    await expect(this.composer).toBeVisible();
  }

  /** The strategy ID created by the last `newChat()` call. */
  lastStrategyId: string | null = null;

  /** Start a fresh conversation so the test is isolated from prior state. */
  async newChat() {
    // Wait for the POST that creates the new strategy to complete.
    // Set up the response listener BEFORE clicking (per Playwright docs).
    const strategyCreated = this.page.waitForResponse(
      (resp) =>
        resp.url().includes("/strategies/open") &&
        resp.request().method() === "POST" &&
        resp.ok(),
    );
    await this.newChatButton.click();
    const resp = await strategyCreated;
    // Capture the strategy ID from the response for test isolation.
    try {
      const body = await resp.json();
      this.lastStrategyId = body?.strategyId ?? body?.id ?? null;
    } catch {
      this.lastStrategyId = null;
    }
    // Now the new conversation exists — wait for the UI to settle.
    await expect(this.sendButton).toBeVisible({ timeout: 10_000 });
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

  async expectIdle() {
    await expect(this.sendButton).toBeVisible({ timeout: 15_000 });
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
    // Planning artifacts show "Apply to strategy" buttons.
    await expect(
      this.page.getByRole("button", { name: /apply to strategy/i }),
    ).toBeVisible({ timeout: 30_000 });
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
