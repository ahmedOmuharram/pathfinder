import type { APIRequestContext, BrowserContext } from "@playwright/test";
import { request } from "@playwright/test";

/**
 * Create an authenticated API client for postcondition verification.
 *
 * Takes the browser context's whole storage state, so the client carries both
 * `pathfinder-auth` (PathFinder identity) and `Authorization` (the registered
 * VEuPathDB token every WDK-backed route needs). This client is for ASSERTING
 * server-side state after UI actions, never for setup.
 */
export async function createApiClient(
  context: BrowserContext,
  baseURL: string,
): Promise<APIRequestContext> {
  // Mutations require the CSRF header (`csrf_middleware` rejects non-GET
  // requests without it), so set it on every request from this client.
  return request.newContext({
    baseURL,
    storageState: await context.storageState(),
    extraHTTPHeaders: { "X-Requested-With": "XMLHttpRequest" },
  });
}

export type ApiClient = APIRequestContext;

export interface PersistedMessage {
  role: "user" | "assistant";
  content: string;
}

interface SnapshotChunk {
  type: string;
  delta?: string;
  message?: { role: string; parts?: { type: string; text?: string }[] };
}

/**
 * Reduce a conversation's persisted event snapshot into role-tagged
 * messages. The conversation detail endpoint no longer embeds messages;
 * chat history is reconstructed from the `events/snapshot` chunk stream
 * (user-message chunks + per-turn assistant text-delta chunks).
 */
export async function fetchConversationMessages(
  api: APIRequestContext,
  conversationId: string | null,
): Promise<PersistedMessage[]> {
  if (conversationId == null) return [];
  const resp = await api.get(`/api/v1/conversations/${conversationId}/events/snapshot`);
  if (!resp.ok()) return [];
  const { chunks } = (await resp.json()) as { chunks: SnapshotChunk[] };
  const messages: PersistedMessage[] = [];
  let assistant = "";
  const flush = () => {
    if (assistant !== "") {
      messages.push({ role: "assistant", content: assistant });
      assistant = "";
    }
  };
  for (const chunk of chunks) {
    if (chunk.type === "user-message") {
      flush();
      const text = (chunk.message?.parts ?? [])
        .filter((p) => p.type === "text")
        .map((p) => p.text ?? "")
        .join("");
      messages.push({ role: "user", content: text });
    } else if (chunk.type === "text-delta") {
      assistant += chunk.delta ?? "";
    } else if (chunk.type === "finish") {
      flush();
    }
  }
  flush();
  return messages;
}

/**
 * Delete all gene sets for the current user via the API.
 *
 * Cleans gene sets across all VEuPathDB sites (default + site-specific)
 * to prevent cross-site pollution between tests.
 *
 * Uses `page.context().request` so cookies are shared with the browser.
 * Call from `beforeEach` in workbench/gene-set specs for test isolation.
 */
export async function clearAllGeneSets(
  context: BrowserContext,
  baseURL: string,
): Promise<void> {
  const req = context.request;
  const siteIds = [undefined, "plasmodb", "toxodb", "cryptodb", "fungidb", "tritrypdb"];
  await Promise.all(
    siteIds.map(async (siteId) => {
      const url =
        siteId != null && siteId !== ""
          ? `${baseURL}/api/v1/gene-sets?siteId=${siteId}`
          : `${baseURL}/api/v1/gene-sets`;
      const listResp = await req.get(url);
      if (!listResp.ok()) return;
      const geneSets = (await listResp.json()) as { id: string }[];
      await Promise.all(
        geneSets.map((gs) =>
          req.delete(`${baseURL}/api/v1/gene-sets/${gs.id}`, {
            headers: { "X-Requested-With": "XMLHttpRequest" },
          }),
        ),
      );
    }),
  );
}
