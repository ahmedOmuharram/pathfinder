"use client";

/**
 * Strategy data-fetching and syncing for the conversation sidebar.
 *
 * Owns the sync/refetch lifecycle, optimistic deletion filtering,
 * and the manual-refresh spinner state.
 */

import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useEffect,
  useRef,
  useState,
  startTransition,
} from "react";
import {
  listDismissedStrategies,
  listStrategies,
  syncWdkStrategies,
} from "@/lib/api/strategies";
import type { Strategy } from "@pathfinder/shared";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/strategy/store";

interface UseStrategyFetchingArgs {
  siteId: string;
  reportError: (message: string) => void;
}

export interface StrategyFetchingResult {
  strategyItems: Strategy[];
  setStrategyItems: Dispatch<SetStateAction<Strategy[]>>;
  dismissedItems: Strategy[];
  setDismissedItems: Dispatch<SetStateAction<Strategy[]>>;
  hasInitiallyLoaded: boolean;
  isSyncing: boolean;
  refreshStrategies: () => Promise<void>;
  refetchStrategies: () => Promise<void>;
  handleManualRefresh: () => Promise<void>;
  /** Mark an ID as recently deleted so stale refetch responses won't re-add it. */
  markAsDeleted: (id: string) => void;
  /** Whether the first fetch has completed (exposed for auto-conversation logic). */
  hasFetched: React.RefObject<boolean>;
}

export function useStrategyFetching({
  siteId,
  reportError,
}: UseStrategyFetchingArgs): StrategyFetchingResult {
  const authVersion = useSessionStore((s) => s.authVersion);
  const draftStrategy = useStrategyStore((s) => s.strategy);

  const [strategyItems, setStrategyItems] = useState<Strategy[]>([]);
  const [dismissedItems, setDismissedItems] = useState<Strategy[]>([]);
  const [isSyncing, setIsSyncing] = useState(false);
  const [hasInitiallyLoaded, setHasInitiallyLoaded] = useState(false);

  // Guards
  const syncInFlight = useRef(false);
  const prevSiteRef = useRef(siteId);
  const hasFetched = useRef(false);
  const recentlyDeletedIds = useRef(new Set<string>());

  // Clear stale items immediately on site change + unblock fetch guard.
  useEffect(() => {
    if (prevSiteRef.current !== siteId) {
      prevSiteRef.current = siteId;
      setStrategyItems([]);
      setHasInitiallyLoaded(false);
      syncInFlight.current = false;
      hasFetched.current = false;
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
        const filteredStrategies = strategies.filter((s) => !excluded.has(s.id));
        useStrategyStore.getState().setStrategies(filteredStrategies);
        setStrategyItems(filteredStrategies);
        const serverDismissedIds = new Set(dismissed.map((s) => s.id));
        setDismissedItems((prev) => {
          const optimisticExtras = prev.filter(
            (s) => excluded.has(s.id) && !serverDismissedIds.has(s.id),
          );
          return [...dismissed, ...optimisticExtras];
        });
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
        if (fetchSite !== prevSiteRef.current) return;
        hasFetched.current = true;
        setHasInitiallyLoaded(true);
        applyFetchResult(strategies, dismissed);
      })
      .catch((err) => {
        console.warn("[ConversationSidebar] Failed to sync strategies:", err);
        reportError(err instanceof Error ? err.message : String(err));
        setHasInitiallyLoaded(true);
      })
      .finally(() => {
        syncInFlight.current = false;
      });
  }, [siteId, applyFetchResult, reportError]);

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
        reportError(err instanceof Error ? err.message : String(err));
        setHasInitiallyLoaded(true);
      })
      .finally(() => {
        syncInFlight.current = false;
      });
  }, [siteId, applyFetchResult, reportError]);

  const handleManualRefresh = useCallback(async () => {
    setIsSyncing(true);
    try {
      await refreshStrategies();
    } finally {
      setIsSyncing(false);
    }
  }, [refreshStrategies]);

  const markAsDeleted = useCallback((id: string) => {
    recentlyDeletedIds.current.add(id);
  }, []);

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
    syncInFlight.current = false;
    void refreshStrategies();
  }, [authVersion, refreshStrategies]);

  // Re-fetch strategies when draft strategy changes (local DB only).
  useEffect(() => {
    if (draftStrategy) {
      void refetchStrategies();
    }
  }, [draftStrategy, refetchStrategies]);

  return {
    strategyItems,
    setStrategyItems,
    dismissedItems,
    setDismissedItems,
    hasInitiallyLoaded,
    isSyncing,
    refreshStrategies,
    refetchStrategies,
    handleManualRefresh,
    markAsDeleted,
    hasFetched,
  };
}
