import { test, expect } from "../fixtures/test";

/**
 * Feature: User data purge — verified against real PostgreSQL + Redis.
 *
 * Tests that DELETE /api/v1/user/data clears ALL data:
 * - strategies (active + dismissed) across all sites
 * - gene sets across all sites
 * - Redis streams
 * - WDK strategies (best-effort)
 */
test.describe("User Data Purge", () => {
  test("purge site data deletes strategies and gene sets for that site only", async ({
    chatPage,
    apiClient,
    sitePicker,
    workbenchSidebarPage,
    page,
    seedData,
  }) => {
    // Create data on plasmodb
    await chatPage.goto();
    await sitePicker.selectSite("plasmodb");
    await chatPage.newChat();
    await chatPage.send("test message for plasmodb");
    await chatPage.expectAssistantMessage(/\[mock\]/);

    // Add a gene set on plasmodb
    await page.goto("/workbench");
    await expect(page.getByRole("heading", { name: /gene sets/i })).toBeVisible();
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Plasmo Genes");
    await page
      .getByLabel(/gene ids/i)
      .fill(seedData.plasmoGenes.slice(0, 2).join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 10_000 });

    // Verify data exists
    const beforeStrategies = await apiClient.get("/api/v1/strategies?siteId=plasmodb");
    expect((await beforeStrategies.json()).length).toBeGreaterThan(0);
    const beforeGeneSets = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    expect((await beforeGeneSets.json()).length).toBeGreaterThan(0);

    // Purge plasmodb data
    const purgeResp = await apiClient.delete("/api/v1/user/data?siteId=plasmodb");
    expect(purgeResp.ok()).toBeTruthy();
    const result = await purgeResp.json();
    expect(result.ok).toBe(true);
    expect(result.deleted.strategies).toBeGreaterThan(0);
    expect(result.deleted.geneSets).toBeGreaterThan(0);

    // Verify data is gone
    const afterStrategies = await apiClient.get("/api/v1/strategies?siteId=plasmodb");
    expect((await afterStrategies.json()).length).toBe(0);
    const afterGeneSets = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    expect((await afterGeneSets.json()).length).toBe(0);
  });

  test("purge ALL data deletes across all sites", async ({
    chatPage,
    apiClient,
    sitePicker,
  }) => {
    // Create data on two different sites
    await chatPage.goto();

    await sitePicker.selectSite("plasmodb");
    await chatPage.newChat();
    await chatPage.send("plasmodb data");
    await chatPage.expectAssistantMessage(/\[mock\]/);

    await sitePicker.selectSite("toxodb");
    await chatPage.newChat();
    await chatPage.send("toxodb data");
    await chatPage.expectAssistantMessage(/\[mock\]/);

    // Verify data on both sites
    const plasmo = await apiClient.get("/api/v1/strategies?siteId=plasmodb");
    expect((await plasmo.json()).length).toBeGreaterThan(0);
    const toxo = await apiClient.get("/api/v1/strategies?siteId=toxodb");
    expect((await toxo.json()).length).toBeGreaterThan(0);

    // Purge ALL (no siteId)
    const purgeResp = await apiClient.delete("/api/v1/user/data");
    expect(purgeResp.ok()).toBeTruthy();
    const result = await purgeResp.json();
    expect(result.ok).toBe(true);
    expect(result.deleted.strategies).toBeGreaterThanOrEqual(2);

    // Both sites empty (active list)
    const afterPlasmo = await apiClient.get("/api/v1/strategies?siteId=plasmodb");
    expect((await afterPlasmo.json()).length).toBe(0);
    const afterToxo = await apiClient.get("/api/v1/strategies?siteId=toxodb");
    expect((await afterToxo.json()).length).toBe(0);

    // Sync-wdk should NOT re-import dismissed strategies into the active list.
    // WDK strategies still exist (deleteWdk=false), but dismissed projections
    // must be skipped by the sync — no new active strategies should appear.
    for (const siteId of ["plasmodb", "toxodb"]) {
      const syncResp = await apiClient.post(
        `/api/v1/strategies/sync-wdk?siteId=${siteId}`,
      );
      if (syncResp.ok()) {
        const synced = (await syncResp.json()) as unknown[];
        expect(
          synced.length,
          `sync-wdk re-imported ${synced.length} active strategies on ${siteId} after dismiss purge`,
        ).toBe(0);
      }
    }
  });

  test("seed all databases then purge deletes everything on every site", async ({
    apiClient,
  }) => {
    test.setTimeout(300_000);
    // Get ALL site IDs (including portal) so we can verify every single one.
    const sitesResp = await apiClient.get("/api/v1/sites");
    const sites = (await sitesResp.json()) as { id: string }[];
    const allSiteIds = sites.map((s) => s.id);

    // Seed all databases — creates strategies + control sets across all sites.
    const seedResp = await apiClient.post("/api/v1/experiments/seed", {
      headers: { Accept: "text/event-stream" },
      timeout: 300_000,
    });
    expect(seedResp.ok()).toBeTruthy();
    const seedBody = await seedResp.text();
    expect(seedBody).toContain("seed_complete");

    // Verify: strategies exist
    const beforeStrategies = await apiClient.get("/api/v1/strategies");
    const beforeList = (await beforeStrategies.json()) as unknown[];
    expect(beforeList.length).toBeGreaterThan(0);
    const strategiesBefore = beforeList.length;

    // Verify: gene sets exist
    const beforeGs = await apiClient.get("/api/v1/gene-sets");
    const beforeGsList = (await beforeGs.json()) as unknown[];
    const geneSetsBefore = beforeGsList.length;

    // Verify: strategies exist on multiple sites (not just one)
    let sitesWithStrategies = 0;
    for (const siteId of allSiteIds) {
      const resp = await apiClient.get(`/api/v1/strategies?siteId=${siteId}`);
      if (resp.ok() && ((await resp.json()) as unknown[]).length > 0) {
        sitesWithStrategies++;
      }
    }
    expect(sitesWithStrategies).toBeGreaterThan(1);

    // Purge ALL data with deleteWdk=true
    const purgeResp = await apiClient.delete("/api/v1/user/data?deleteWdk=true");
    expect(purgeResp.ok()).toBeTruthy();
    const result = (await purgeResp.json()) as {
      ok: boolean;
      deleted: {
        strategies: number;
        wdkStrategies: number;
        geneSets: number;
      };
    };
    expect(result.ok).toBe(true);
    // Background auto-import may create additional projections between list
    // and purge, so the count can be higher than strategiesBefore.
    expect(result.deleted.strategies).toBeGreaterThanOrEqual(strategiesBefore);
    expect(result.deleted.geneSets).toBeGreaterThanOrEqual(geneSetsBefore);
    expect(result.deleted.wdkStrategies).toBeGreaterThan(0);

    // Verify: ALL local strategies gone
    const afterStrategies = await apiClient.get("/api/v1/strategies");
    expect(((await afterStrategies.json()) as unknown[]).length).toBe(0);

    // Verify: ALL gene sets gone
    const afterGs = await apiClient.get("/api/v1/gene-sets");
    expect(((await afterGs.json()) as unknown[]).length).toBe(0);

    // Verify: dismissed list empty
    const afterDismissed = await apiClient.get("/api/v1/strategies/dismissed");
    if (afterDismissed.ok()) {
      expect(((await afterDismissed.json()) as unknown[]).length).toBe(0);
    }

    // CRITICAL: sync-wdk on EVERY site (including portal) must return zero.
    // This catches strategies surviving on WDK after purge.
    for (const siteId of allSiteIds) {
      const syncResp = await apiClient.post(
        `/api/v1/strategies/sync-wdk?siteId=${siteId}`,
      );
      if (syncResp.ok()) {
        const synced = (await syncResp.json()) as unknown[];
        expect(
          synced.length,
          `sync-wdk re-imported ${synced.length} strategies from ${siteId} after purge — WDK deletion failed for this site`,
        ).toBe(0);
      }
    }

    // Verify per-site: no strategies on any individual site
    for (const siteId of allSiteIds) {
      const resp = await apiClient.get(`/api/v1/strategies?siteId=${siteId}`);
      if (resp.ok()) {
        expect(
          ((await resp.json()) as unknown[]).length,
          `strategies still exist on ${siteId} after purge`,
        ).toBe(0);
      }
    }
  });

  test("purge deletes auto-built strategies with wdkStrategyId and gene sets", async ({
    chatPage,
    apiClient,
  }) => {
    // Seed: create a strategy with auto-build (real WDK strategy + gene set)
    await chatPage.goto();
    await chatPage.newChat();
    await chatPage.send("create step");
    await chatPage.expectAssistantMessage(/\[mock\]/i);
    await chatPage.expectIdle();

    // Verify auto-build created real data
    const strategyId = chatPage.lastStrategyId;
    const stratResp = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    const strategy = await stratResp.json();
    expect(strategy.wdkStrategyId).toBeTruthy();

    const gsResp = await apiClient.get("/api/v1/gene-sets");
    const geneSets = await gsResp.json();
    expect(geneSets.length).toBeGreaterThan(0);

    // Purge ALL data with deleteWdk=true to fully remove everything.
    const purgeResp = await apiClient.delete("/api/v1/user/data?deleteWdk=true");
    expect(purgeResp.ok()).toBeTruthy();
    const result = await purgeResp.json();
    expect(result.ok).toBe(true);
    expect(result.deleted.strategies).toBeGreaterThan(0);
    expect(result.deleted.geneSets).toBeGreaterThan(0);

    // Verify: strategy hard-deleted (404)
    const afterStrat = await apiClient.get(`/api/v1/strategies/${strategyId}`);
    expect(afterStrat.status()).toBe(404);

    // Verify: gene sets gone
    const afterGs = await apiClient.get("/api/v1/gene-sets");
    expect((await afterGs.json()).length).toBe(0);

    // Verify: strategy list empty
    const afterList = await apiClient.get("/api/v1/strategies");
    expect((await afterList.json()).length).toBe(0);
  });
});
