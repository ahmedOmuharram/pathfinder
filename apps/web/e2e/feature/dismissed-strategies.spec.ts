import { test, expect } from "../fixtures/test";
import type { ChatPage } from "../pages/chat.page";
import type { SidebarPage } from "../pages/sidebar.page";
import type { ApiClient } from "../fixtures/api-client";

/**
 * Feature: Dismissed (soft-deleted) strategies.
 *
 * WDK-linked strategies are soft-deleted (dismissed) rather than hard-deleted
 * when the user clicks Delete without the "Sync delete to WDK" setting enabled.
 * The dismissed section in the sidebar shows these strategies with a Restore
 * button to bring them back.
 *
 * Strategies are created via chat UI (immediately visible in sidebar), then a
 * unique wdkStrategyId is PATCHed on to simulate a WDK-linked strategy.
 */

/**
 * Helper: create a strategy via chat UI and PATCH a unique wdkStrategyId
 * onto it, making it behave as a WDK-linked strategy for delete semantics.
 */
async function makeWdkLinked(
  chatPage: ChatPage,
  sidebarPage: SidebarPage,
  apiClient: ApiClient,
  message = "conversation for dismissed test",
): Promise<string> {
  await chatPage.send(message);
  await chatPage.expectAssistantMessage(/\[mock\]/);
  await expect(sidebarPage.items.first()).toBeVisible({ timeout: 15_000 });

  const strategyId = await sidebarPage.firstConversationId();

  const uniqueWdkId = Math.floor(Date.now() / 1000) + Math.floor(Math.random() * 10000);
  const patchResp = await apiClient.patch(`/api/v1/strategies/${strategyId}`, {
    data: { wdkStrategyId: uniqueWdkId },
  });
  expect(patchResp.ok()).toBeTruthy();

  return strategyId;
}

/** Start a new chat and wait for the strategy creation to complete. */
async function startNewChat(
  page: import("@playwright/test").Page,
  sidebarPage: import("../pages/sidebar.page").SidebarPage,
) {
  const ready = page.waitForResponse(
    (resp) =>
      resp.url().includes("/strategies/open") &&
      resp.request().method() === "POST" &&
      resp.ok(),
  );
  await sidebarPage.createNew();
  await ready;
}

/** Wait for a DELETE 204 response targeting a specific strategy. */
function waitForDelete(page: import("@playwright/test").Page, strategyId: string) {
  return page.waitForResponse(
    (resp) =>
      resp.url().includes(`/strategies/${strategyId}`) &&
      resp.request().method() === "DELETE" &&
      resp.status() === 204,
  );
}

/** Wait for a POST restore response targeting a specific strategy. */
function waitForRestore(page: import("@playwright/test").Page, strategyId: string) {
  return page.waitForResponse(
    (resp) =>
      resp.url().includes(`/strategies/${strategyId}/restore`) &&
      resp.request().method() === "POST" &&
      resp.ok(),
  );
}

// ── Basic flows ────────────────────────────────────────────────────

test.describe("Dismissed Strategies", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ chatPage }) => {
    await chatPage.goto();
    await chatPage.newChat();
  });

  test("soft-deleted WDK strategy appears in dismissed section", async ({
    chatPage,
    sidebarPage,
    apiClient,
    page,
  }) => {
    const strategyId = await makeWdkLinked(chatPage, sidebarPage, apiClient);

    const deleteCompleted = waitForDelete(page, strategyId);
    await sidebarPage.delete(strategyId);
    await deleteCompleted;

    await expect(sidebarPage.item(strategyId)).not.toBeVisible({
      timeout: 10_000,
    });
    await sidebarPage.expectDismissedCount(1);

    await sidebarPage.expandDismissed();
    await sidebarPage.expectDismissedItemVisible(strategyId);

    const dismissedResp = await apiClient.get("/api/v1/strategies/dismissed");
    expect(dismissedResp.ok()).toBeTruthy();
    const dismissed = (await dismissedResp.json()) as { id: string }[];
    expect(dismissed.some((d) => d.id === strategyId)).toBeTruthy();
  });

  test("restore dismissed strategy returns to main list", async ({
    chatPage,
    sidebarPage,
    apiClient,
    page,
  }) => {
    const strategyId = await makeWdkLinked(chatPage, sidebarPage, apiClient);

    const deleteCompleted = waitForDelete(page, strategyId);
    await sidebarPage.delete(strategyId);
    await deleteCompleted;

    await expect(sidebarPage.item(strategyId)).not.toBeVisible({
      timeout: 10_000,
    });
    await sidebarPage.expectDismissedCount(1);

    await sidebarPage.expandDismissed();

    const restoreCompleted = waitForRestore(page, strategyId);
    await sidebarPage.restoreDismissed(strategyId);
    await restoreCompleted;

    await expect(sidebarPage.item(strategyId)).toBeVisible({
      timeout: 15_000,
    });
    await sidebarPage.expectNoDismissedSection();

    const strategyResp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    expect(strategyResp.ok()).toBeTruthy();

    const dismissedResp = await apiClient.get("/api/v1/strategies/dismissed");
    expect(dismissedResp.ok()).toBeTruthy();
    const dismissed = (await dismissedResp.json()) as { id: string }[];
    expect(dismissed.some((d) => d.id === strategyId)).toBeFalsy();
  });
});

// ── Complex flows ──────────────────────────────────────────────────

test.describe("Dismissed Strategies — complex flows", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ chatPage }) => {
    await chatPage.goto();
    await chatPage.newChat();
  });

  test("delete → restore → delete → restore round-trip", async ({
    chatPage,
    sidebarPage,
    apiClient,
    page,
  }) => {
    const strategyId = await makeWdkLinked(chatPage, sidebarPage, apiClient);

    // ── First dismiss ──
    let deleteCompleted = waitForDelete(page, strategyId);
    await sidebarPage.delete(strategyId);
    await deleteCompleted;

    await expect(sidebarPage.item(strategyId)).not.toBeVisible({
      timeout: 10_000,
    });
    await sidebarPage.expectDismissedCount(1);

    // ── First restore ──
    await sidebarPage.expandDismissed();
    let restoreCompleted = waitForRestore(page, strategyId);
    await sidebarPage.restoreDismissed(strategyId);
    await restoreCompleted;

    await expect(sidebarPage.item(strategyId)).toBeVisible({
      timeout: 15_000,
    });
    await sidebarPage.expectNoDismissedSection();

    // ── Second dismiss ──
    deleteCompleted = waitForDelete(page, strategyId);
    await sidebarPage.delete(strategyId);
    await deleteCompleted;

    await expect(sidebarPage.item(strategyId)).not.toBeVisible({
      timeout: 10_000,
    });
    await sidebarPage.expectDismissedCount(1);

    // ── Second restore ──
    await sidebarPage.expandDismissed();
    restoreCompleted = waitForRestore(page, strategyId);
    await sidebarPage.restoreDismissed(strategyId);
    await restoreCompleted;

    await expect(sidebarPage.item(strategyId)).toBeVisible({
      timeout: 15_000,
    });
    await sidebarPage.expectNoDismissedSection();

    // API confirms fully active.
    const resp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    expect(resp.ok()).toBeTruthy();
  });

  test("multiple dismissed strategies — restore one at a time", async ({
    chatPage,
    sidebarPage,
    apiClient,
    page,
  }) => {
    // Create first WDK strategy.
    const id1 = await makeWdkLinked(
      chatPage,
      sidebarPage,
      apiClient,
      "first strategy for multi-dismiss",
    );

    // Create second WDK strategy (new chat first so sidebar has 2 items).
    await startNewChat(page, sidebarPage);
    const id2 = await makeWdkLinked(
      chatPage,
      sidebarPage,
      apiClient,
      "second strategy for multi-dismiss",
    );

    // Dismiss both.
    let deleteCompleted = waitForDelete(page, id2);
    await sidebarPage.delete(id2);
    await deleteCompleted;

    await expect(sidebarPage.item(id2)).not.toBeVisible({ timeout: 10_000 });
    await sidebarPage.expectDismissedCount(1);

    // Wait for id1 to be visible after sidebar refetch before deleting it.
    await expect(sidebarPage.item(id1)).toBeVisible({ timeout: 10_000 });

    deleteCompleted = waitForDelete(page, id1);
    await sidebarPage.delete(id1);
    await deleteCompleted;

    await expect(sidebarPage.item(id1)).not.toBeVisible({ timeout: 10_000 });
    await sidebarPage.expectDismissedCount(2);

    // Expand dismissed — both visible.
    await sidebarPage.expandDismissed();
    await sidebarPage.expectDismissedItemVisible(id1);
    await sidebarPage.expectDismissedItemVisible(id2);

    // Restore one — count drops to 1.
    const restoreCompleted = waitForRestore(page, id1);
    await sidebarPage.restoreDismissed(id1);
    await restoreCompleted;

    await expect(sidebarPage.item(id1)).toBeVisible({ timeout: 15_000 });
    await sidebarPage.expectDismissedCount(1);

    // Restore the other — dismissed section disappears.
    const restoreCompleted2 = waitForRestore(page, id2);
    await sidebarPage.restoreDismissed(id2);
    await restoreCompleted2;

    await expect(sidebarPage.item(id2)).toBeVisible({ timeout: 15_000 });
    await sidebarPage.expectNoDismissedSection();
  });

  test("restored strategy is fully functional — can receive messages", async ({
    chatPage,
    sidebarPage,
    apiClient,
    page,
  }) => {
    const strategyId = await makeWdkLinked(
      chatPage,
      sidebarPage,
      apiClient,
      "strategy to restore and reuse",
    );

    // Dismiss it.
    const deleteCompleted = waitForDelete(page, strategyId);
    await sidebarPage.delete(strategyId);
    await deleteCompleted;

    await expect(sidebarPage.item(strategyId)).not.toBeVisible({
      timeout: 10_000,
    });
    await sidebarPage.expectDismissedCount(1);

    // Restore it.
    await sidebarPage.expandDismissed();
    const restoreCompleted = waitForRestore(page, strategyId);
    await sidebarPage.restoreDismissed(strategyId);
    await restoreCompleted;

    await expect(sidebarPage.item(strategyId)).toBeVisible({
      timeout: 15_000,
    });

    // Select the restored strategy.
    await sidebarPage.selectConversation(strategyId);

    // Send a new message to verify the conversation is fully functional.
    await chatPage.send("follow-up after restore");
    await chatPage.expectAssistantMessage(/follow-up after restore/);

    // API confirms strategy still exists and is accessible.
    const resp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    expect(resp.ok()).toBeTruthy();
  });
});
