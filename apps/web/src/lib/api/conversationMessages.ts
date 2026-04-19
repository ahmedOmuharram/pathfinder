import { queryOptions } from "@tanstack/react-query";
import type { UIMessage } from "ai";
import { z } from "zod";

import { requestJson } from "./http";

const UIMessagePartSchema = z.looseObject({
  type: z.string(),
});

const PersistedUIMessageSchema = z.object({
  id: z.string(),
  role: z.enum(["system", "user", "assistant"]),
  parts: z.array(UIMessagePartSchema),
  metadata: z.unknown().optional(),
});

const PersistedMessageListSchema = z.array(PersistedUIMessageSchema);

export async function listConversationMessages(
  conversationId: string,
): Promise<UIMessage[]> {
  const rows = await requestJson(
    PersistedMessageListSchema,
    `/api/v1/conversations/${conversationId}/messages`,
  );
  return rows as unknown as UIMessage[];
}

export function conversationMessagesOptions(conversationId: string) {
  return queryOptions({
    queryKey: ["conversations", conversationId, "messages"] as const,
    queryFn: () => listConversationMessages(conversationId),
    staleTime: Infinity,
    gcTime: Infinity,
  });
}
