"use client";

/**
 * Data-fetching and list-building logic for the conversation sidebar.
 *
 * Owns strategy items, syncing state, search query, and the
 * filtered conversation list.
 */

import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  startTransition,
} from "react";
import {
  listDismissedStrategies,
  listStrategies,
  openStrategy,
  syncWdkStrategies,
} from "@/lib/api/strategies";
import { DEFAULT_STREAM_NAME, type Strategy } from "@pathfinder/shared";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/strategy/store";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import { resolveActiveConversation } from "@/features/sidebar/utils/resolveActiveConversation";

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
  reportError: _reportError,
}: UseConversationSidebarDataArgs): ConversationSidebarData {
  // --- Store selectors ---
  const strategyId = useSessionStore((s) => s.strategyId);
  const setStrategyId = useSessionStore((s) => s.setStrategyId);
  const authVersion = useSessionStore((s) => s.authVersion);
  const veupathdbSignedIn = useSessionStore((s) => s.veupathdbSignedIn);
  const chatIsStreaming = useSessionStore((s) => s.chatIsStreaming);

  const draftStrategy = useStrategyStore((s) => s.strategy);

  // --- Local state ---
  const [strategyItems, setStrategyItems] = useState<Strategy[]>([]);
  const [query, setQuery] = useState("");
  const [isSyncing, setIsSyncing] = useState(false);
  const [hasInitiallyLoaded, setHasInitiallyLoaded] = useState(false);
  const [dismissedItems, setDismissedItems] = useState<Strategy[]>([]);

  // --- Data fetching ---

  // Guard against concurrent sync calls (e.g. two useEffects firing on mount).
  const syncInFlight = useRef(false);
  const prevSiteRef = useRef(siteId);
  // Track whether the initial fetch has completed (to avoid premature auto-create).
  const hasFetched = useRef(false);
  // Guard against concurrent auto-create calls.
  const autoCreateInFlight = useRef(false);
  // Guard: when the user explicitly clicks "New Chat", suppress auto-pick
  // until the new conversation POST completes.
  const newConversationInFlight = useRef(false);
  // IDs of strategies that were optimistically removed by a delete workflow.
  // Refetch responses filter these out so stale data doesn't re-add them.
  // Cleared when the delete's own refetch completes with committed data.
  const recentlyDeletedIds = useRef(new Set<string>());

  // Clear stale items immediately on site change + unblock fetch guard.
  useEffect(() => {
    if (prevSiteRef.current !== siteId) {
      prevSiteRef.current = siteId;
      setStrategyItems([]);
      setHasInitiallyLoaded(false);
      syncInFlight.current = false;
      hasFetched.current = false;
      autoCreateInFlight.current = false;
    }
  }, [siteId]);

  /** Apply fetched data, filtering out any IDs in the recentlyDeletedIds set
   *  so that stale refetch responses don't undo optimistic deletions.
   *  For dismissed items, preserves optimistic additions that the server
   *  hasn't seen yet (the soft-delete may not have committed when the
   *  refetch query ran). */
  const applyFetchResult = useCallback(
    (strategies: Strategy[], dismissed: Strategy[]) => {
      const excluded = recentlyDeletedIds.current;
      if (excluded.size > 0) {
        // Filter recently-deleted IDs from the active list.
        const filteredStrategies = strategies.filter((s) => !excluded.has(s.id));
        useStrategyStore.getState().setStrategies(filteredStrategies);
        setStrategyItems(filteredStrategies);
        // Merge dismissed: keep optimistic additions that the server hasn't
        // picked up yet (their ID is in excluded but not in the server's
        // dismissed list).
        const serverDismissedIds = new Set(dismissed.map((s) => s.id));
        setDismissedItems((prev) => {
          const optimisticExtras = prev.filter(
            (s) => excluded.has(s.id) && !serverDismissedIds.has(s.id),
          );
          return [...dismissed, ...optimisticExtras];
        });
        // Clear IDs whose deletion the server has acknowledged (the ID no
        // longer appears in the active list).
        for (const id of excluded) {
          if (!strategies.some((s) => s.id === id)) {
            excluded.delete(id);
          }
        }
      } else {
        useStrategyStore.getState().setStrategies(strategies);
        setStrategyItems(strategies);
        setDismissedItems(dismissed);
      }
    },
    [],
  );

  const refreshStrategies = useCallback(() => {
    if (syncInFlight.current) return Promise.resolve();
    syncInFlight.current = true;
    const fetchSite = siteId;
    return Promise.all([syncWdkStrategies(siteId), listDismissedStrategies(siteId)])
      .then(([strategies, dismissed]) => {
        // Discard if site changed while fetch was in-flight.
        if (fetchSite !== prevSiteRef.current) return;
        hasFetched.current = true;
        setHasInitiallyLoaded(true);
        applyFetchResult(strategies, dismissed);
      })
      .catch((err) => {
        console.warn("[ConversationSidebar] Failed to sync strategies:", err);
        // Unblock the sidebar even on error — otherwise it stays in
        // loading state indefinitely until a retry succeeds.
        setHasInitiallyLoaded(true);
      })
      .finally(() => {
        syncInFlight.current = false;
      });
  }, [siteId, applyFetchResult]);

  const refetchStrategies = useCallback(() => {
    if (syncInFlight.current) return Promise.resolve();
    syncInFlight.current = true;
    const fetchSite = siteId;
    return Promise.all([listStrategies(siteId), listDismissedStrategies(siteId)])
      .then(([strategies, dismissed]) => {
        if (fetchSite !== prevSiteRef.current) return;
        hasFetched.current = true;
        setHasInitiallyLoaded(true);
        applyFetchResult(strategies, dismissed);
      })
      .catch((err) => {
        console.warn("[ConversationSidebar] Failed to fetch strategies:", err);
        setHasInitiallyLoaded(true);
      })
      .finally(() => {
        syncInFlight.current = false;
      });
  }, [siteId, applyFetchResult]);

  const handleManualRefresh = useCallback(async () => {
    setIsSyncing(true);
    try {
      await refreshStrategies();
    } finally {
      setIsSyncing(false);
    }
  }, [refreshStrategies]);

  // Ensure there's always an active conversation (strategy).
  // Core invariant: NEVER switch away from a set strategyId. The data-loading
  // layer validates it (404 → clear). This prevents race conditions during
  // rapid refresh where the sidebar list isn't populated yet.
  const ensureActiveConversation = useCallback(async () => {
    // Don't auto-pick while the user is explicitly creating a new conversation
    // or while chat is streaming (the chat flow creates its own conversation).
    if (newConversationInFlight.current || chatIsStreaming) return;

    const action = resolveActiveConversation({
      strategyId,
      hasAuth: veupathdbSignedIn,
      strategyItems,
      hasFetched: hasFetched.current,
    });

    switch (action.type) {
      case "keep":
      case "wait":
        return;

      case "pick":
        setStrategyId(action.strategyId);
        return;

      case "create": {
        if (autoCreateInFlight.current) return;
        autoCreateInFlight.current = true;
        try {
          const res = await openStrategy({ siteId });
          const now = new Date().toISOString();
          setStrategyItems((prev) => [
            ...prev,
            {
              id: res.strategyId,
              name: DEFAULT_STREAM_NAME,
              updatedAt: now,
              createdAt: now,
              siteId,
              recordType: null,
              steps: [],
              rootStepId: null,
              stepCount: 0,
              isSaved: false,
            },
          ]);
          // Only set if no other flow (e.g. chat send) grabbed strategyId
          // while the async openStrategy was in-flight.
          const currentId = useSessionStore.getState().strategyId;
          if (currentId == null || currentId === "") {
            setStrategyId(res.strategyId);
          }
        } catch (err) {
          console.warn("[ensureActiveConversation] Failed to auto-create:", err);
        } finally {
          autoCreateInFlight.current = false;
        }
        return;
      }
    }
  }, [
    veupathdbSignedIn,
    chatIsStreaming,
    strategyId,
    strategyItems,
    setStrategyId,
    siteId,
    setStrategyItems,
  ]);

  // --- Effects ---

  // Refresh on mount / site change
  useEffect(() => {
    startTransition(() => {
      void refreshStrategies();
    });
  }, [refreshStrategies]);

  // Retry sync after auth cookie refresh (signaled by authVersion bump).
  const prevAuthVersionRef = useRef(authVersion);
  useEffect(() => {
    if (prevAuthVersionRef.current === authVersion) return;
    prevAuthVersionRef.current = authVersion;
    // Reset the in-flight guard so the retry can proceed.
    syncInFlight.current = false;
    void refreshStrategies();
  }, [authVersion, refreshStrategies]);

  // Re-fetch strategies when draft strategy changes (local DB only — no WDK sync needed).
  // Only refetch when a strategy is actively loaded (non-null), not when cleared.
  // Clearing (null) happens during delete/restore workflows where optimistic updates
  // already handle the state, and a refetch here would race with those updates.
  useEffect(() => {
    if (draftStrategy) {
      void refetchStrategies();
    }
  }, [draftStrategy, refetchStrategies]);

  // Ensure there's always an active conversation selected
  useEffect(() => {
    startTransition(() => {
      void ensureActiveConversation();
    });
  }, [ensureActiveConversation]);

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

  // Filter
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversations, query]);

  const setNewConversationInFlight = useCallback((inFlight: boolean) => {
    newConversationInFlight.current = inFlight;
  }, []);

  const markAsDeleted = useCallback((id: string) => {
    recentlyDeletedIds.current.add(id);
  }, []);

  return {
    filtered,
    hasConversations: conversations.length > 0,
    hasInitiallyLoaded,
    query,
    setQuery,
    isSyncing,
    refreshStrategies,
    refetchStrategies,
    handleManualRefresh,
    strategyItems,
    setStrategyItems,
    setNewConversationInFlight,
    dismissedConversations,
    setDismissedItems,
    markAsDeleted,
  };
}
