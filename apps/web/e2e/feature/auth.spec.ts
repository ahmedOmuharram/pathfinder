import { test, expect } from "../fixtures/test";

test.describe("Auth", () => {
  test("authenticated state shows full UI with working API access", async ({
    chatPage,
    authPage,
    sitePicker,
    settingsPage,
    apiClient,
  }) => {
    await chatPage.goto();

    // UI: Signed in — no login modal, composer visible
    await authPage.expectSignedIn();

    // UI: Site picker shows default site
    await sitePicker.expectCurrentSite("veupathdb");

    // UI: Settings accessible with all tabs
    await settingsPage.open();
    await settingsPage.expectAllTabsVisible();
    await settingsPage.close();

    // API postcondition: real endpoints work
    const strategiesResp = await apiClient.get("/api/v1/conversations");
    expect(strategiesResp.ok()).toBeTruthy();

    const sitesResp = await apiClient.get("/api/v1/sites");
    expect(sitesResp.ok()).toBeTruthy();
    const sites = await sitesResp.json();
    expect(sites.length).toBeGreaterThan(0);
    const siteIds = sites.map((s: { id: string }) => s.id);
    expect(siteIds).toContain("plasmodb");
    expect(siteIds).toContain("toxodb");

    const modelsResp = await apiClient.get("/api/v1/models");
    expect(modelsResp.ok()).toBeTruthy();
    const models = await modelsResp.json();
    expect(models.defaultProvider).toBeTruthy();
  });

  test("page reload preserves session — UI and API intact", async ({
    chatPage,
    authPage,
    sidebarPage,
    page,
    apiClient,
  }) => {
    await chatPage.goto();
    await chatPage.newChat();

    // Send a message to create state. (Keep it plainly biological — phrases
    // like "session persistence" trip the PIGuard safety screen.)
    await chatPage.send("show me kinase genes");
    await chatPage.expectAssistantMessage(/\[mock\]/);
    await chatPage.expectIdle();

    // Verify sidebar shows conversation
    await sidebarPage.expectAtLeastOneConversation();

    // API: get strategy count before reload
    const beforeResp = await apiClient.get("/api/v1/conversations");
    expect(beforeResp.ok()).toBeTruthy();
    const beforeCount = (await beforeResp.json()).length;

    // Reload
    await page.reload();
    await expect(page.getByTestId("message-composer")).toBeVisible({ timeout: 15_000 });

    // UI: Still signed in — composer visible, message still there
    await authPage.expectSignedIn();
    await expect(
      page.locator(".is-user").filter({ hasText: "show me kinase genes" }),
    ).toBeVisible({ timeout: 15_000 });

    // UI: Sidebar still shows conversations
    await sidebarPage.expectAtLeastOneConversation();

    // API: Same strategy count — no data loss
    const afterResp = await apiClient.get("/api/v1/conversations");
    expect(afterResp.ok()).toBeTruthy();
    expect((await afterResp.json()).length).toBe(beforeCount);
  });
});
