import type { ChatListItem } from "@/lib/api/chats";

export interface ConversationItem {
  id: string;
  title: string;
  updatedAt: string;
  siteId: string;
  isDismissed: boolean;
  isSaved: boolean;
  stepCount: number;
  experimentId: string | null;
  /** Full backend payload — kept so downstream handlers can inspect server state. */
  chat: ChatListItem;
}

export function chatToConversationItem(chat: ChatListItem): ConversationItem {
  return {
    id: chat.id,
    title: chat.name.trim() === "" ? "New conversation" : chat.name,
    updatedAt: chat.updatedAt,
    siteId: chat.siteId,
    isDismissed: chat.dismissedAt !== null,
    isSaved: chat.isSaved,
    stepCount: chat.stepCount,
    experimentId: chat.experimentId,
    chat,
  };
}
