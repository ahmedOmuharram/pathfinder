import { test, expect } from "../fixtures/test";

/**
 * Feature: branching + switching between conversations.
 *
 * Branching forks the conversation into a new chat from a chosen message.
 * Switching back to the original conversation must preserve its messages.
 */
test.describe("Branch Switch", () => {
  test.beforeEach(async ({ chatPage }) => {
    await chatPage.goto();
    await chatPage.newChat();
  });

  test("switching back to original branch preserves prior messages", async ({
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
    const assistantReply = page
      .locator(".is-assistant")
      .filter({ hasText: /\[mock\]/ });
    await assistantReply.hover();
    await assistantReply
      .getByRole("button", { name: /branch to a new chat from here/i })
      .click();
    await forkResponse;
    await expect(page).not.toHaveURL(
      new RegExp(`/conversation/${originalId}(?:$|[?#])`),
    );

    // Switch back to the original conversation — its messages are intact.
    await page.goto(`/veupathdb/conversation/${originalId}`);
    await expect(chatPage.composer).toBeVisible({ timeout: 15_000 });
    await expect(
      page.locator(".is-user").filter({ hasText: "show me kinase genes" }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      page.locator(".is-assistant").filter({ hasText: /\[mock\]/ }),
    ).toBeVisible({ timeout: 15_000 });
  });
});
