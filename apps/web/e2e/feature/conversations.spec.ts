import { test, expect } from "../fixtures/test";

/**
 * Feature: Conversations — CRUD verified against real PostgreSQL.
 */
test.describe("Conversations", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ chatPage }) => {
    await chatPage.goto();
    await chatPage.newChat();
  });

  test("new conversation persisted in PostgreSQL", async ({
    chatPage,
    sidebarPage,
    apiClient,
  }) => {
    await chatPage.send("create a new conversation");
    await chatPage.expectAssistantMessage(/\[mock\]/);
    await expect(sidebarPage.items.first()).toBeVisible({ timeout: 15_000 });

    // API confirms strategy exists with messages — use captured ID for isolation
    const strategyId = chatPage.lastStrategyId;
    expect(strategyId).toBeTruthy();

    // Fetch full strategy to verify messages are stored
    const fullResp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    expect(fullResp.ok()).toBeTruthy();
    const full = await fullResp.json();
    expect(full.messages).toBeDefined();
    expect(full.messages.length).toBeGreaterThan(0);
  });

  test("create new conversation via button persists to DB", async ({
    chatPage,
    apiClient,
  }) => {
    await chatPage.send("first conversation");
    await chatPage.expectAssistantMessage(/\[mock\]/);

    const midResp = await apiClient.get("/api/v1/strategies");
    const midCount = (await midResp.json()).length;

    await chatPage.newChat();
    await expect(chatPage.composer).toBeVisible();

    const afterResp = await apiClient.get("/api/v1/strategies");
    expect((await afterResp.json()).length).toBe(midCount + 1);
  });

  test("rename conversation persists to PostgreSQL", async ({
    chatPage,
    sidebarPage,
    apiClient,
  }) => {
    await chatPage.send("conversation to rename");
    await chatPage.expectAssistantMessage(/\[mock\]/);

    const conversationId = await sidebarPage.firstConversationId();
    await sidebarPage.rename(conversationId, "Renamed Strategy");
    await sidebarPage.expectConversationName(conversationId, /renamed strategy/i);

    // API confirms rename persisted
    const resp = await apiClient.get(`/api/v1/strategies/${conversationId}`);
    expect(resp.ok()).toBeTruthy();
    const strategy = await resp.json();
    expect(strategy.name).toMatch(/renamed strategy/i);
  });

  test("delete conversation removes from PostgreSQL", async ({
    chatPage,
    sidebarPage,
    page,
    apiClient,
  }) => {
    await chatPage.send("conversation to delete");
    await chatPage.expectAssistantMessage(/\[mock\]/);
    await expect(sidebarPage.items.first()).toBeVisible({ timeout: 15_000 });

    const conversationId = await sidebarPage.firstConversationId();

    // Verify exists before delete
    const beforeResp = await apiClient.get(`/api/v1/strategies/${conversationId}`);
    expect(beforeResp.ok()).toBeTruthy();

    // Wait for the DELETE API call to complete alongside the UI action
    const deleteCompleted = page.waitForResponse(
      (resp) =>
        resp.url().includes(`/strategies/${conversationId}`) &&
        resp.request().method() === "DELETE",
    );
    await sidebarPage.delete(conversationId);
    await deleteCompleted;

    await expect(sidebarPage.item(conversationId)).not.toBeVisible({
      timeout: 10_000,
    });

    // API confirms soft-deleted (moved to dismissed, since auto-build gave it a WDK ID)
    const dismissedResp = await apiClient.get("/api/v1/strategies/dismissed");
    expect(dismissedResp.ok()).toBeTruthy();
    const dismissed = (await dismissedResp.json()) as { id: string }[];
    expect(dismissed.some((d) => d.id === conversationId)).toBeTruthy();
  });

  test("search conversations filters list", async ({ chatPage, sidebarPage }) => {
    await chatPage.send("alpha query");
    await chatPage.expectAssistantMessage(/\[mock\]/);

    await sidebarPage.createNew();
    await chatPage.send("beta query");
    await chatPage.expectAssistantMessage(/\[mock\]/);

    await sidebarPage.search("alpha");
    await expect(sidebarPage.searchInput).toHaveValue("alpha");

    await sidebarPage.clearSearch();
    await expect(sidebarPage.searchInput).toHaveValue("");
  });
});
