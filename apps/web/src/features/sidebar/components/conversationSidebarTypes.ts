import type { ConversationSummary } from "@/lib/api/conversations";

export interface ConversationItem {
  id: string;
  title: string;
  updatedAt: string;
  siteId: string;
  isDismissed: boolean;
  isSaved: boolean;
  stepCount: number;
  experimentId: string | null;
  parentConversationId: string | null;
  parentMessageId: string | null;
  /** Full backend payload — kept so downstream handlers can inspect server state. */
  chat: ConversationSummary;
}

export function chatToConversationItem(chat: ConversationSummary): ConversationItem {
  return {
    id: chat.id,
    title: chat.name.trim() === "" ? "New conversation" : chat.name,
    updatedAt: chat.updatedAt,
    siteId: chat.siteId,
    isDismissed: chat.dismissedAt != null,
    isSaved: chat.isSaved ?? false,
    stepCount: chat.stepCount ?? 0,
    experimentId: chat.experimentId ?? null,
    parentConversationId: chat.parentConversationId ?? null,
    parentMessageId: chat.parentMessageId ?? null,
    chat,
  };
}
