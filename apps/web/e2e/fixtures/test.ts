import { test as base } from "@playwright/test";
import { type ApiClient, createApiClient } from "./api-client";
import { type SeedData, fetchSeedData } from "./seed";
import { ChatPage } from "../pages/chat.page";
import { SidebarPage } from "../pages/sidebar.page";
import { WorkbenchSidebarPage } from "../pages/workbench-sidebar.page";
import { WorkbenchMainPage } from "../pages/workbench-main.page";
import { GraphPage } from "../pages/graph.page";
import { SitePickerComponent } from "../pages/site-picker.page";
import { SettingsPage } from "../pages/settings.page";
import { AuthPage } from "../pages/auth.page";
import { GeneSearchSidebar } from "../pages/gene-search.page";
import * as fs from "node:fs";
import * as path from "node:path";

/** Test-scoped fixtures (fresh per test). */
type TestFixtures = {
  _autoCleanup: void;
  chatPage: ChatPage;
  sidebarPage: SidebarPage;
  workbenchSidebarPage: WorkbenchSidebarPage;
  workbenchMainPage: WorkbenchMainPage;
  graphPage: GraphPage;
  sitePicker: SitePickerComponent;
  settingsPage: SettingsPage;
  authPage: AuthPage;
  geneSearch: GeneSearchSidebar;
  apiClient: ApiClient;
};

/** Worker-scoped fixtures (shared across tests in a worker). */
type WorkerFixtures = {
  seedData: SeedData;
  workerStorageState: string;
};

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";

export const test = base.extend<TestFixtures, WorkerFixtures>({
  // ── Worker-scoped ──────────────────────────────────────────────

  /**
   * Per-worker authentication.
   *
   * Each Playwright worker calls `/dev/login?user_id=worker-{N}` to get
   * its own isolated user. This means workers never share gene sets,
   * strategies, or conversations — eliminating all cross-worker pollution.
   */
  workerStorageState: [
    async ({ browser }, use, workerInfo) => {
      const id = workerInfo.workerIndex;
      const dir = path.resolve("e2e/.auth");
      const fileName = path.join(dir, `worker-${id}.json`);

      // Always re-authenticate to ensure a clean session.
      fs.mkdirSync(dir, { recursive: true });

      const page = await browser.newPage({ storageState: undefined });
      await page.goto(BASE_URL);

      const resp = await page
        .context()
        .request.post(`${BASE_URL}/api/v1/dev/login?user_id=worker-${id}`);
      if (!resp.ok()) {
        throw new Error(`dev-login failed for worker-${id}: ${resp.status()}`);
      }

      // Clean up stale data from previous runs for THIS worker's user.
      const req = page.context().request;
      const strategiesResp = await req.get(`${BASE_URL}/api/v1/strategies`);
      if (strategiesResp.ok()) {
        const strategies = (await strategiesResp.json()) as { id: string }[];
        await Promise.all(
          strategies.map((s) =>
            req.delete(`${BASE_URL}/api/v1/strategies/${s.id}?deleteFromWdk=true`),
          ),
        );
      }
      // Also purge dismissed (soft-deleted) strategies from prior runs.
      const dismissedResp = await req.get(`${BASE_URL}/api/v1/strategies/dismissed`);
      if (dismissedResp.ok()) {
        const dismissed = (await dismissedResp.json()) as { id: string }[];
        await Promise.all(
          dismissed.map((d) =>
            req.delete(`${BASE_URL}/api/v1/strategies/${d.id}?deleteFromWdk=true`),
          ),
        );
      }
      // Clean gene sets across ALL sites (default + site-specific).
      const workerSiteIds = [
        undefined,
        "plasmodb",
        "toxodb",
        "cryptodb",
        "fungidb",
        "tritrypdb",
      ];
      await Promise.all(
        workerSiteIds.map(async (siteId) => {
          const url = siteId
            ? `${BASE_URL}/api/v1/gene-sets?siteId=${siteId}`
            : `${BASE_URL}/api/v1/gene-sets`;
          const resp = await req.get(url);
          if (resp.ok()) {
            const geneSets = (await resp.json()) as { id: string }[];
            await Promise.all(
              geneSets.map((gs) => req.delete(`${BASE_URL}/api/v1/gene-sets/${gs.id}`)),
            );
          }
        }),
      );

      await page.context().storageState({ path: fileName });
      await page.close();

      await use(fileName);
    },
    { scope: "worker" },
  ],

  /**
   * Override Playwright's built-in storageState so every test in this
   * worker uses the per-worker auth cookie.
   */
  storageState: ({ workerStorageState }, use) => use(workerStorageState),

  seedData: [
    async ({}, use) => {
      const data = await fetchSeedData(BASE_URL);
      await use(data);
    },
    { scope: "worker" },
  ],

  // ── Test-scoped: auto-cleanup ─────────────────────────────────

  /** Clear gene sets, strategies, and dismissed strategies before each test. */
  _autoCleanup: [
    async ({ context }, use) => {
      const req = context.request;
      // Clean gene sets across ALL sites (default + site-specific).
      const allSiteIds = [
        undefined,
        "plasmodb",
        "toxodb",
        "cryptodb",
        "fungidb",
        "tritrypdb",
      ];
      await Promise.all(
        allSiteIds.map(async (siteId) => {
          const url = siteId
            ? `${BASE_URL}/api/v1/gene-sets?siteId=${siteId}`
            : `${BASE_URL}/api/v1/gene-sets`;
          const resp = await req.get(url);
          if (resp.ok()) {
            const geneSets = (await resp.json()) as { id: string }[];
            await Promise.all(
              geneSets.map((gs) => req.delete(`${BASE_URL}/api/v1/gene-sets/${gs.id}`)),
            );
          }
        }),
      );
      // Force hard-delete (deleteFromWdk=true) so WDK-linked strategies
      // don't get soft-deleted and accumulate in the dismissed list.
      const strategiesResp = await req.get(`${BASE_URL}/api/v1/strategies`);
      if (strategiesResp.ok()) {
        const strategies = (await strategiesResp.json()) as { id: string }[];
        await Promise.all(
          strategies.map((s) =>
            req.delete(`${BASE_URL}/api/v1/strategies/${s.id}?deleteFromWdk=true`),
          ),
        );
      }
      // Purge dismissed (soft-deleted) strategies from prior tests/retries.
      const dismissedResp = await req.get(`${BASE_URL}/api/v1/strategies/dismissed`);
      if (dismissedResp.ok()) {
        const dismissed = (await dismissedResp.json()) as { id: string }[];
        await Promise.all(
          dismissed.map((d) =>
            req.delete(`${BASE_URL}/api/v1/strategies/${d.id}?deleteFromWdk=true`),
          ),
        );
      }
      await use(undefined);
    },
    { auto: true },
  ],

  // ── Test-scoped: page objects ──────────────────────────────────
  chatPage: async ({ page }, use) => {
    await use(new ChatPage(page));
  },

  sidebarPage: async ({ page }, use) => {
    await use(new SidebarPage(page));
  },

  workbenchSidebarPage: async ({ page }, use) => {
    await use(new WorkbenchSidebarPage(page));
  },

  workbenchMainPage: async ({ page }, use) => {
    await use(new WorkbenchMainPage(page));
  },

  graphPage: async ({ page }, use) => {
    await use(new GraphPage(page));
  },

  sitePicker: async ({ page }, use) => {
    await use(new SitePickerComponent(page));
  },

  settingsPage: async ({ page }, use) => {
    await use(new SettingsPage(page));
  },

  authPage: async ({ page }, use) => {
    await use(new AuthPage(page));
  },

  geneSearch: async ({ page }, use) => {
    await use(new GeneSearchSidebar(page));
  },

  // ── Test-scoped: API client for postcondition verification ─────
  apiClient: async ({ page, context }, use) => {
    const baseURL = page.url().startsWith("http")
      ? new URL(page.url()).origin
      : BASE_URL;
    const client = await createApiClient(context, baseURL);
    await use(client);
    await client.dispose();
  },
});

export { expect } from "@playwright/test";
