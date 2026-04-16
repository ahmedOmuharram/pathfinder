/**
 * Chat (conversation) API client.
 *
 * Sidebar SSOT: the chats listing / dismissed listing / rename / dismiss /
 * restore / delete / duplicate endpoints.
 */
import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { requestJson, requestVoid } from "./http";

const ChatListItemSchema = z.object({
  id: z.uuid(),
  name: z.string(),
  siteId: z.string(),
  experimentId: z.string().nullable(),
  wdkStrategyId: z.number().int().nullable(),
  isSaved: z.boolean(),
  stepCount: z.number().int(),
  estimatedSize: z.number().int().nullable(),
  dismissedAt: z.string().nullable(),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export type ChatListItem = z.infer<typeof ChatListItemSchema>;

const ChatListSchema = z.array(ChatListItemSchema);

const ChatDuplicateResponseSchema = z.object({
  id: z.uuid(),
  name: z.string(),
});

export type ChatDuplicateResponse = z.infer<typeof ChatDuplicateResponseSchema>;

export async function listChats(siteId?: string | null): Promise<ChatListItem[]> {
  return requestJson(
    ChatListSchema,
    "/api/v1/chats",
    siteId != null && siteId !== "" ? { query: { siteId } } : {},
  );
}

export async function listDismissedChats(
  siteId?: string | null,
): Promise<ChatListItem[]> {
  return requestJson(
    ChatListSchema,
    "/api/v1/chats/dismissed",
    siteId != null && siteId !== "" ? { query: { siteId } } : {},
  );
}

export async function renameChat(
  chatId: string,
  name: string,
): Promise<ChatListItem> {
  return requestJson(ChatListItemSchema, `/api/v1/chats/${chatId}`, {
    method: "PATCH",
    body: { name },
  });
}

export async function setChatSaved(
  chatId: string,
  isSaved: boolean,
): Promise<ChatListItem> {
  return requestJson(ChatListItemSchema, `/api/v1/chats/${chatId}`, {
    method: "PATCH",
    body: { isSaved },
  });
}

export async function dismissChat(chatId: string): Promise<void> {
  await requestVoid(`/api/v1/chats/${chatId}/dismiss`, { method: "POST" });
}

export async function restoreChat(chatId: string): Promise<void> {
  await requestVoid(`/api/v1/chats/${chatId}/restore`, { method: "POST" });
}

export async function deleteChat(chatId: string): Promise<void> {
  await requestVoid(`/api/v1/chats/${chatId}`, { method: "DELETE" });
}

export async function duplicateChat(
  chatId: string,
): Promise<ChatDuplicateResponse> {
  return requestJson(
    ChatDuplicateResponseSchema,
    `/api/v1/chats/${chatId}/duplicate`,
    { method: "POST" },
  );
}

export function chatListOptions(siteId: string) {
  return queryOptions({
    queryKey: ["chats", "list", siteId] as const,
    queryFn: () => listChats(siteId),
  });
}

export function dismissedChatsOptions(siteId: string) {
  return queryOptions({
    queryKey: ["chats", "dismissed", siteId] as const,
    queryFn: () => listDismissedChats(siteId),
  });
}
