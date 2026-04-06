"use client";

/**
 * Data-fetching and list-building logic for the conversation sidebar.
 *
 * Composes sub-hooks for strategy fetching and auto-conversation
 * selection, and owns the filtered conversation list.
 */

import { type Dispatch, type SetStateAction, useMemo } from "react";
import type { Strategy } from "@pathfinder/shared";
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
  refreshStrategies: () => Promise<void>;
  /** Lightweight re-fetch from local DB only (no WDK sync). */
  refetchStrategies: () => Promise<void>;
  handleManualRefresh: () => Promise<void>;
  /** Exposed for the actions hook to perform optimistic strategy-list updates. */
  strategyItems: Strategy[];
  setStrategyItems: Dispatch<SetStateAction<Strategy[]>>;
  /**
   * Signal that a new conversation is being created (async POST in flight).
   * While true, `ensureActiveConversation` will not auto-pick a strategy,
   * preventing it from overriding the user's explicit "New Chat" action.
   */
  setNewConversationInFlight: (inFlight: boolean) => void;
  /** Dismissed (soft-deleted) strategies. */
  dismissedConversations: ConversationItem[];
  /** Optimistic setter for dismissed items (used by restore workflow). */
  setDismissedItems: Dispatch<SetStateAction<Strategy[]>>;
  /** Mark an ID as recently deleted so stale refetch responses won't re-add it. */
  markAsDeleted: (id: string) => void;
}

export function useConversationSidebarData({
  siteId,
  reportError,
}: UseConversationSidebarDataArgs): ConversationSidebarData {
  // --- Sub-hooks ---
  const fetching = useStrategyFetching({ siteId, reportError });

  const autoConversation = useAutoConversation({
    siteId,
    strategyItems: fetching.strategyItems,
    setStrategyItems: fetching.setStrategyItems,
    hasFetched: fetching.hasFetched,
  });

  // Destructure to stable references for useMemo deps.
  const { strategyItems, dismissedItems } = fetching;

  // --- Build conversation list ---
  const conversations: ConversationItem[] = useMemo(() => {
    const strategies: ConversationItem[] = strategyItems.map((s) => ({
      id: s.id,
      kind: "strategy" as const,
      title: s.name,
      updatedAt: s.updatedAt,
      siteId: s.siteId,
      strategyItem: s,
    }));

    return strategies.sort(
      (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
    );
  }, [strategyItems]);

  const dismissedConversations: ConversationItem[] = useMemo(() => {
    return dismissedItems.map((s) => ({
      id: s.id,
      kind: "strategy" as const,
      title: s.name,
      updatedAt: s.updatedAt,
      siteId: s.siteId,
      strategyItem: s,
    }));
  }, [dismissedItems]);

  // --- Search filter ---
  const { query, setQuery, filtered } = useSearchFilter(conversations);

  return {
    filtered,
    hasConversations: conversations.length > 0,
    hasInitiallyLoaded: fetching.hasInitiallyLoaded,
    query,
    setQuery,
    isSyncing: fetching.isSyncing,
    refreshStrategies: fetching.refreshStrategies,
    refetchStrategies: fetching.refetchStrategies,
    handleManualRefresh: fetching.handleManualRefresh,
    strategyItems: fetching.strategyItems,
    setStrategyItems: fetching.setStrategyItems,
    setNewConversationInFlight: autoConversation.setNewConversationInFlight,
    dismissedConversations,
    setDismissedItems: fetching.setDismissedItems,
    markAsDeleted: fetching.markAsDeleted,
  };
}
