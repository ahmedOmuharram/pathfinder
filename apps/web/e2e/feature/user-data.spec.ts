import { test, expect } from "../fixtures/test";
import { MOCK_PLAN_PROMPT } from "../fixtures/mock-prompts";

interface SeedFrame {
  type: string;
  message: string;
}

interface SeedItemErrorFrame extends SeedFrame {
  type: "seed_item_error";
  name: string;
  error: string;
}

interface SeedCompleteFrame extends SeedFrame {
  type: "seed_complete";
  total: number;
  strategiesCreated: number;
  controlSetsCreated: number;
  failed: number;
  error: string | null;
}

/** The typed frames of one `/api/v1/experiments/seed` stream. */
function seedFrames(body: string): SeedFrame[] {
  return body
    .split("\n")
    .filter((line) => line.startsWith("data: ") && line.trim() !== "data: [DONE]")
    .map((line) => JSON.parse(line.slice("data: ".length)) as SeedFrame);
}

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
    await chatPage.newChat("plasmodb");
    await chatPage.send("test message for plasmodb");
    await chatPage.expectAssistantMessage(/\[mock\]/);

    // Add a gene set on plasmodb (site-explicit — bare /workbench would
    // redirect to the default site and create the set on the wrong one).
    await page.goto("/plasmodb/workbench");
    await expect(page.getByRole("heading", { name: /gene sets/i })).toBeVisible();
    await workbenchSidebarPage.openAddModal();
    await page.getByLabel(/name/i).fill("Plasmo Genes");
    await page
      .getByLabel(/gene ids/i)
      .fill(seedData.plasmoGenes.slice(0, 2).join("\n"));
    await page.getByRole("button", { name: /add gene set/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 10_000 });

    // Verify data exists
    const beforeStrategies = await apiClient.get(
      "/api/v1/conversations?siteId=plasmodb",
    );
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
    const afterStrategies = await apiClient.get(
      "/api/v1/conversations?siteId=plasmodb",
    );
    expect((await afterStrategies.json()).length).toBe(0);
    const afterGeneSets = await apiClient.get("/api/v1/gene-sets?siteId=plasmodb");
    expect((await afterGeneSets.json()).length).toBe(0);
  });

  test("purge ALL data deletes across all sites", async ({
    chatPage,
    apiClient,
    sitePicker,
  }) => {
    // The shared WDK account carries strategies this test did not create.
    // Import them first so the purge dismisses their projections; the
    // invariant under test is that a dismissed projection is not resurrected.
    const knownWdkIds = new Set<number>();
    for (const siteId of ["plasmodb", "toxodb"]) {
      const preSync = await apiClient.post(
        `/api/v1/conversations/sync-wdk?siteId=${siteId}`,
      );
      if (preSync.ok()) {
        const imported = (await preSync.json()) as { wdkStrategyId?: number }[];
        for (const conv of imported) {
          if (conv.wdkStrategyId) knownWdkIds.add(conv.wdkStrategyId);
        }
      }
    }

    // Create data on two different sites
    await chatPage.goto();

    await sitePicker.selectSite("plasmodb");
    await chatPage.newChat("plasmodb");
    await chatPage.send("plasmodb data");
    await chatPage.expectAssistantMessage(/\[mock\]/);

    await sitePicker.selectSite("toxodb");
    await chatPage.newChat("toxodb");
    await chatPage.send("toxodb data");
    await chatPage.expectAssistantMessage(/\[mock\]/);

    // Verify data on both sites
    const plasmo = await apiClient.get("/api/v1/conversations?siteId=plasmodb");
    expect((await plasmo.json()).length).toBeGreaterThan(0);
    const toxo = await apiClient.get("/api/v1/conversations?siteId=toxodb");
    expect((await toxo.json()).length).toBeGreaterThan(0);

    // Purge ALL (no siteId)
    const purgeResp = await apiClient.delete("/api/v1/user/data");
    expect(purgeResp.ok()).toBeTruthy();
    const result = await purgeResp.json();
    expect(result.ok).toBe(true);
    expect(result.deleted.strategies).toBeGreaterThanOrEqual(2);

    // Both sites empty (active list)
    const afterPlasmo = await apiClient.get("/api/v1/conversations?siteId=plasmodb");
    expect((await afterPlasmo.json()).length).toBe(0);
    const afterToxo = await apiClient.get("/api/v1/conversations?siteId=toxodb");
    expect((await afterToxo.json()).length).toBe(0);

    // Sync-wdk must NOT re-import dismissed strategies into the active list.
    // The WDK strategies still exist (deleteWdk=false), so the check is on
    // identity, not count: no strategy imported before the purge may come
    // back. Strategies another worker creates concurrently are not ours.
    for (const siteId of ["plasmodb", "toxodb"]) {
      const syncResp = await apiClient.post(
        `/api/v1/conversations/sync-wdk?siteId=${siteId}`,
      );
      if (syncResp.ok()) {
        const synced = (await syncResp.json()) as { wdkStrategyId?: number }[];
        const resurrected = synced.filter(
          (conv) => conv.wdkStrategyId && knownWdkIds.has(conv.wdkStrategyId),
        );
        expect(
          resurrected.length,
          `sync-wdk resurrected ${resurrected.length} dismissed strategies on ${siteId} after purge`,
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
    // A seed that creates nothing still ends with `seed_complete`, so the
    // counters decide, and the item errors name what VEuPathDB refused.
    const frames = seedFrames(await seedResp.text());
    const itemErrors = frames
      .filter((f): f is SeedItemErrorFrame => f.type === "seed_item_error")
      .map((f) => `${f.name}: ${f.error}`);
    const complete = frames.find(
      (f): f is SeedCompleteFrame => f.type === "seed_complete",
    );
    if (complete === undefined) {
      throw new Error(
        `seed stream carried no seed_complete frame; item errors: ${itemErrors.join(" | ")}`,
      );
    }
    expect(complete.error, `seed reported a top-level failure`).toBe(null);
    expect(
      complete.strategiesCreated,
      `seed created 0 of ${String(complete.total)} strategies (${String(complete.failed)} failed): ${itemErrors.slice(0, 5).join(" | ")}`,
    ).toBeGreaterThan(0);

    // Verify: strategies exist. Their WDK ids are the purge's target set:
    // the shared account also holds strategies this run did not create, and
    // the purge must not touch those.
    const beforeStrategies = await apiClient.get("/api/v1/conversations");
    const beforeList = (await beforeStrategies.json()) as {
      wdkStrategyId?: number;
    }[];
    expect(beforeList.length).toBeGreaterThan(0);
    const strategiesBefore = beforeList.length;
    const ourWdkIds = new Set<number>();
    for (const conv of beforeList) {
      if (conv.wdkStrategyId) ourWdkIds.add(conv.wdkStrategyId);
    }
    expect(ourWdkIds.size).toBeGreaterThan(0);

    // Verify: gene sets exist
    const beforeGs = await apiClient.get("/api/v1/gene-sets");
    const beforeGsList = (await beforeGs.json()) as unknown[];
    const geneSetsBefore = beforeGsList.length;

    // Verify: strategies exist on multiple sites (not just one)
    let sitesWithStrategies = 0;
    for (const siteId of allSiteIds) {
      const resp = await apiClient.get(`/api/v1/conversations?siteId=${siteId}`);
      if (resp.ok() && ((await resp.json()) as unknown[]).length > 0) {
        sitesWithStrategies++;
      }
    }
    expect(sitesWithStrategies).toBeGreaterThan(1);

    // Purge ALL data with deleteWdk=true. Deleting every seeded WDK strategy
    // across all sites is slow, so allow well beyond the default request timeout.
    const purgeResp = await apiClient.delete("/api/v1/user/data?deleteWdk=true", {
      timeout: 240_000,
    });
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
    const afterStrategies = await apiClient.get("/api/v1/conversations");
    expect(((await afterStrategies.json()) as unknown[]).length).toBe(0);

    // Verify: ALL gene sets gone
    const afterGs = await apiClient.get("/api/v1/gene-sets");
    expect(((await afterGs.json()) as unknown[]).length).toBe(0);

    // Verify: dismissed list empty
    const afterDismissed = await apiClient.get("/api/v1/conversations/dismissed");
    if (afterDismissed.ok()) {
      expect(((await afterDismissed.json()) as unknown[]).length).toBe(0);
    }

    // CRITICAL: sync-wdk on EVERY site (including portal) must not bring back
    // any strategy this run created. The check is on identity, not count: the
    // shared account holds other strategies, and those may import freely.
    for (const siteId of allSiteIds) {
      const syncResp = await apiClient.post(
        `/api/v1/conversations/sync-wdk?siteId=${siteId}`,
      );
      if (syncResp.ok()) {
        const synced = (await syncResp.json()) as { wdkStrategyId?: number }[];
        const survivors = synced.filter(
          (conv) => conv.wdkStrategyId && ourWdkIds.has(conv.wdkStrategyId),
        );
        expect(
          survivors.length,
          `${survivors.length} purged strategies survived on WDK for ${siteId} — WDK deletion failed for this site`,
        ).toBe(0);
      }
    }

    // Verify per-site: none of the purged strategies is listed anywhere.
    for (const siteId of allSiteIds) {
      const resp = await apiClient.get(`/api/v1/conversations?siteId=${siteId}`);
      if (resp.ok()) {
        const listed = (await resp.json()) as { wdkStrategyId?: number }[];
        const survivors = listed.filter(
          (conv) => conv.wdkStrategyId && ourWdkIds.has(conv.wdkStrategyId),
        );
        expect(
          survivors.length,
          `purged strategies still listed on ${siteId} after purge`,
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
    // A build prompt ends on the verification digest, not the plain echo.
    await chatPage.send(MOCK_PLAN_PROMPT);
    await chatPage.expectVerificationSuccess();
    await chatPage.expectIdle();

    // Verify auto-build created real data
    const strategyId = chatPage.lastStrategyId;
    const stratResp = await apiClient.get(`/api/v1/conversations/${strategyId}`);
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
    const afterStrat = await apiClient.get(`/api/v1/conversations/${strategyId}`);
    expect(afterStrat.status()).toBe(404);

    // Verify: gene sets gone
    const afterGs = await apiClient.get("/api/v1/gene-sets");
    expect((await afterGs.json()).length).toBe(0);

    // Verify: strategy list empty
    const afterList = await apiClient.get("/api/v1/conversations");
    expect((await afterList.json()).length).toBe(0);
  });
});
