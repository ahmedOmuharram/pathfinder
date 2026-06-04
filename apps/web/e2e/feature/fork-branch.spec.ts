import { test, expect } from "../fixtures/test";

/**
 * Feature: branching a conversation from a message.
 *
 * Branching is a per-message action ("Branch to a new chat from here" on an
 * assistant reply) that forks the conversation into a brand-new chat, copying
 * the prior context. Verified end-to-end against the real fork endpoint.
 */
test.describe("Fork Branch", () => {
  test.beforeEach(async ({ chatPage }) => {
    await chatPage.goto();
    await chatPage.newChat();
  });

  test("user forks from a message and lands in a new branched conversation", async ({
    chatPage,
    page,
  }) => {
    await chatPage.send("show me kinase genes");
    await chatPage.expectAssistantMessage(/\[mock\]/);
    await chatPage.expectIdle();

    const originalId = chatPage.lastStrategyId;
    expect(originalId).toBeTruthy();

    // Branch from the assistant reply into a new chat.
    const forkResponse = page.waitForResponse(
      (r) =>
        /\/api\/v1\/conversations\/[^/]+\/fork$/.test(r.url()) &&
        r.request().method() === "POST",
    );
    await page.locator(".is-assistant").first().hover();
    await page
      .getByRole("button", { name: /branch to a new chat from here/i })
      .first()
      .click();
    const fork = await forkResponse;
    expect(fork.ok()).toBeTruthy();

    // Navigated to a new conversation, distinct from the original.
    await expect(page).toHaveURL(/\/conversation\/[0-9a-f-]+/);
    await expect(page).not.toHaveURL(
      new RegExp(`/conversation/${originalId}(?:$|[?#])`),
    );

    // The branched conversation keeps the prior user message.
    await expect(
      page.locator(".is-user").filter({ hasText: "show me kinase genes" }),
    ).toBeVisible({ timeout: 15_000 });
  });
});
