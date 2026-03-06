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
import { openStrategy, syncWdkStrategies } from "@/lib/api/client";
import { DEFAULT_STREAM_NAME, type Strategy } from "@pathfinder/shared";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/useStrategyStore";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import { resolveActiveConversation } from "@/features/sidebar/utils/resolveActiveConversation";

export interface UseConversationSidebarDataArgs {
  siteId: string;
  reportError: (message: string) => void;
}

export interface ConversationSidebarData {
  /** Filtered conversation list (by search query). */
  filtered: ConversationItem[];
  /** Whether there are any conversations at all (ignoring search). */
  hasConversations: boolean;
  query: string;
  setQuery: (q: string) => void;
  isSyncing: boolean;
  refreshStrategies: () => Promise<void>;
  handleManualRefresh: () => Promise<void>;
  /** Exposed for the actions hook to perform optimistic strategy-list updates. */
  strategyItems: Strategy[];
  setStrategyItems: Dispatch<SetStateAction<Strategy[]>>;
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

  const draftStrategy = useStrategyStore((s) => s.strategy);

  // --- Local state ---
  const [strategyItems, setStrategyItems] = useState<Strategy[]>([]);
  const [query, setQuery] = useState("");
  const [isSyncing, setIsSyncing] = useState(false);

  // --- Data fetching ---

  // Guard against concurrent sync calls (e.g. two useEffects firing on mount).
  const syncInFlight = useRef(false);
  const prevSiteRef = useRef(siteId);
  // Track whether the initial fetch has completed (to avoid premature auto-create).
  const hasFetched = useRef(false);
  // Guard against concurrent auto-create calls.
  const autoCreateInFlight = useRef(false);

  // Clear stale items immediately on site change + unblock fetch guard.
  useEffect(() => {
    if (prevSiteRef.current !== siteId) {
      prevSiteRef.current = siteId;
      setStrategyItems([]);
      syncInFlight.current = false;
      hasFetched.current = false;
      autoCreateInFlight.current = false;
    }
  }, [siteId]);

  const refreshStrategies = useCallback(() => {
    if (syncInFlight.current) return Promise.resolve();
    syncInFlight.current = true;
    const fetchSite = siteId;
    return syncWdkStrategies(siteId)
      .then((strategies) => {
        // Discard if site changed while fetch was in-flight.
        if (fetchSite !== prevSiteRef.current) return;
        hasFetched.current = true;
        // Populate the global store so @-mentions and experiment import
        // can read the same data (single source of truth).
        useStrategyStore.getState().setStrategies(strategies);
        setStrategyItems(strategies);
      })
      .catch((err) => {
        console.warn("[ConversationSidebar] Failed to sync strategies:", err);
      })
      .finally(() => {
        syncInFlight.current = false;
      });
  }, [siteId]);

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
          setStrategyItems([
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
          setStrategyId(res.strategyId);
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

  // Re-fetch strategies when draft strategy changes
  useEffect(() => {
    void refreshStrategies();
  }, [draftStrategy?.id, draftStrategy?.updatedAt, refreshStrategies]);

  // Ensure there's always an active conversation selected
  useEffect(() => {
    startTransition(() => {
      ensureActiveConversation();
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

  // Filter
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversations, query]);

  return {
    filtered,
    hasConversations: conversations.length > 0,
    query,
    setQuery,
    isSyncing,
    refreshStrategies,
    handleManualRefresh,
    strategyItems,
    setStrategyItems,
  };
}
