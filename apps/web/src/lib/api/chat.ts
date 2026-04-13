/**
 * Chat history fetcher.
 *
 * Hits `GET /api/v1/chats/:id/messages` which returns the AI-SDK wire-format
 * array of `PathfinderUIMessage`s for a chat. On a 404 (endpoint or chat not
 * found) we treat the result as an empty history — the backend endpoint may
 * not yet exist during the chat-overhaul migration and the frontend should
 * degrade gracefully rather than throw.
 *
 * This fetcher intentionally does NOT use `requestJson` / Zod validation:
 * the wire shape here is an opaque AI-SDK `UIMessage[]` whose `parts` union
 * is already type-checked at the consumer (see `PartRenderer`), and adding a
 * Zod schema mirror would duplicate the shared `PathfinderUIMessage` type in
 * a second source of truth.
 */

import type { PathfinderUIMessage } from "@pathfinder/shared";

export async function fetchChatHistory(
  chatId: string,
): Promise<PathfinderUIMessage[]> {
  const resp = await fetch(
    `/api/v1/chats/${encodeURIComponent(chatId)}/messages`,
    {
      credentials: "include",
      headers: { accept: "application/json" },
    },
  );
  if (!resp.ok) {
    if (resp.status === 404) return [];
    throw new Error(`fetchChatHistory failed: ${resp.status}`);
  }
  const data = (await resp.json()) as PathfinderUIMessage[];
  return data;
}
