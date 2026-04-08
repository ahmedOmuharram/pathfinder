"use client";

/**
 * Data-fetching and list-building logic for the conversation sidebar.
 *
 * Composes sub-hooks for strategy fetching and auto-conversation
 * selection, and owns the filtered conversation list.
 *
 * No setter shims — sub-hooks that need cache access use useQueryClient() directly.
 */

import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import { useStrategyFetching } from "@/features/sidebar/hooks/useStrategyFetching";
import { useAutoConversation } from "@/features/sidebar/hooks/useAutoConversation";
import { useSearchFilter } from "@/features/sidebar/hooks/useSearchFilter";

interface UseConversationSidebarDataArgs {
  siteId: string;
  reportError: (message: string) => void;
}

interface ConversationSidebarData {
  /** Filtered conversation list (by search query). */
  filtered: ConversationItem[];
  /** Whether there are any conversations at all (ignoring search). */
  hasConversations: boolean;
  /** False until the first successful fetch completes. */
  hasInitiallyLoaded: boolean;
  query: string;
  setQuery: (q: string) => void;
  isSyncing: boolean;
  invalidateStrategies: () => Promise<void>;
  handleManualRefresh: () => Promise<void>;
  /** Dismissed (soft-deleted) strategies. */
  dismissedConversations: ConversationItem[];
  /**
   * Signal that a new conversation is being created (async POST in flight).
   * While true, `ensureActiveConversation` will not auto-pick a strategy,
   * preventing it from overriding the user's explicit "New Chat" action.
   */
  setNewConversationInFlight: (inFlight: boolean) => void;
}

export function useConversationSidebarData({
  siteId,
  reportError,
}: UseConversationSidebarDataArgs): ConversationSidebarData {
  // --- Sub-hooks ---
  const fetching = useStrategyFetching({ siteId, reportError });

  const autoConversation = useAutoConversation({
    siteId,
    strategyItems: fetching.strategies,
    isFetched: fetching.isFetched,
  });

  const { strategies, dismissedStrategies } = fetching;

  // --- Build conversation list ---
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

  // --- Search filter ---
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
    setNewConversationInFlight: autoConversation.setNewConversationInFlight,
  };
}
