"use client";

import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import { useStrategyFetching } from "@/features/sidebar/hooks/useStrategyFetching";
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
  const fetching = useStrategyFetching({ siteId });

  const { strategies, dismissedStrategies } = fetching;

  const conversations: ConversationItem[] = strategies
    .map((s) => ({
      id: s.id,
      kind: "strategy" as const,
      title: s.name,
      updatedAt: s.updatedAt,
      siteId: s.siteId,
      strategyItem: s,
    }))
    .sort(
      (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
    );

  const dismissedConversations: ConversationItem[] = dismissedStrategies.map((s) => ({
    id: s.id,
    kind: "strategy" as const,
    title: s.name,
    updatedAt: s.updatedAt,
    siteId: s.siteId,
    strategyItem: s,
  }));

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
