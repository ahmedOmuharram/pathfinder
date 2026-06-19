import { z } from "zod";

import { requestJson } from "./http";

const conversationDuplicateSchema = z.object({
  id: z.string(),
  name: z.string(),
});

export type ConversationDuplicate = z.infer<typeof conversationDuplicateSchema>;

/** Duplicate a whole conversation (incl. its strategy) into a new copy. */
export async function duplicateConversation(
  conversationId: string,
): Promise<ConversationDuplicate> {
  return requestJson(
    conversationDuplicateSchema,
    `/api/v1/conversations/${conversationId}/duplicate`,
    { method: "POST" },
  );
}
