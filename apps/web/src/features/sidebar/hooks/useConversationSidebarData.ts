"use client";

import {
  chatToConversationItem,
  type ConversationItem,
} from "@/features/sidebar/components/conversationSidebarTypes";
import { useChatListFetching } from "@/features/sidebar/hooks/useChatListFetching";
import { useSearchFilter } from "@/features/sidebar/hooks/useSearchFilter";

interface UseConversationSidebarDataArgs {
  siteId: string;
}

interface ConversationSidebarData {
  filtered: ConversationItem[];
  hasConversations: boolean;
  hasInitiallyLoaded: boolean;
  query: string;
  setQuery: (q: string) => void;
  isSyncing: boolean;
  invalidateStrategies: () => Promise<void>;
  handleManualRefresh: () => Promise<void>;
  dismissedConversations: ConversationItem[];
}

export function useConversationSidebarData({
  siteId,
}: UseConversationSidebarDataArgs): ConversationSidebarData {
  const fetching = useChatListFetching({ siteId });

  const conversations: ConversationItem[] = fetching.chats
    .map(chatToConversationItem)
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());

  const dismissedConversations: ConversationItem[] =
    fetching.dismissedChats.map(chatToConversationItem);

  const { query, setQuery, filtered } = useSearchFilter(conversations);

  return {
    filtered,
    hasConversations: conversations.length > 0,
    hasInitiallyLoaded: fetching.isFetched,
    query,
    setQuery,
    isSyncing: fetching.isSyncing,
    invalidateStrategies: fetching.invalidate,
    handleManualRefresh: fetching.handleManualRefresh,
    dismissedConversations,
  };
}
