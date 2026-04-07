"use client";

/**
 * Strategy data-fetching and syncing for the conversation sidebar.
 *
 * Uses TanStack Query for the strategies list and dismissed list.
 * Returns read-only data and invalidation functions — consumers
 * that need optimistic cache updates use useQueryClient() directly.
 */

import { useCallback, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { strategiesListOptions, dismissedStrategiesOptions } from "@/lib/api/strategies";
import type { Strategy } from "@pathfinder/shared";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/strategy/store";

interface UseStrategyFetchingArgs {
  siteId: string;
  reportError: (message: string) => void;
}

export interface StrategyFetchingResult {
  strategies: Strategy[];
  dismissedStrategies: Strategy[];
  isLoading: boolean;
  isFetched: boolean;
  isSyncing: boolean;
  invalidate: () => Promise<void>;
  handleManualRefresh: () => Promise<void>;
}

export function useStrategyFetching({
  siteId,
  reportError,
}: UseStrategyFetchingArgs): StrategyFetchingResult {
  const veupathdbSignedIn = useSessionStore((s) => s.veupathdbSignedIn);
  const authStatusKnown = useSessionStore((s) => s.authStatusKnown);
  const draftStrategy = useStrategyStore((s) => s.strategy);
  const queryClient = useQueryClient();

  const [isSyncing, setIsSyncing] = useState(false);

  const queryEnabled = authStatusKnown && veupathdbSignedIn && siteId !== "";

  const listOpts = strategiesListOptions(siteId);
  const dismissedOpts = dismissedStrategiesOptions(siteId);

  // --- TanStack Query: strategies list ---
  const strategiesQuery = useQuery({
    ...listOpts,
    enabled: queryEnabled,
  });

  // --- TanStack Query: dismissed strategies ---
  const dismissedQuery = useQuery({
    ...dismissedOpts,
    enabled: queryEnabled,
  });

  // Report errors from TQ queries.
  useEffect(() => {
    if (strategiesQuery.error) {
      console.warn("[ConversationSidebar] Failed to sync strategies:", strategiesQuery.error);
      reportError(
        strategiesQuery.error instanceof Error
          ? strategiesQuery.error.message
          : String(strategiesQuery.error),
      );
    }
  }, [strategiesQuery.error, reportError]);

  useEffect(() => {
    if (dismissedQuery.error) {
      console.warn("[ConversationSidebar] Failed to fetch dismissed:", dismissedQuery.error);
      reportError(
        dismissedQuery.error instanceof Error
          ? dismissedQuery.error.message
          : String(dismissedQuery.error),
      );
    }
  }, [dismissedQuery.error, reportError]);

  // --- Derived data from TQ cache ---
  const strategies: Strategy[] = strategiesQuery.data ?? [];
  const dismissedStrategies: Strategy[] = dismissedQuery.data ?? [];

  // --- Invalidation-based refresh ---
  const invalidate = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: listOpts.queryKey }),
      queryClient.invalidateQueries({ queryKey: dismissedOpts.queryKey }),
    ]);
  }, [queryClient, listOpts.queryKey, dismissedOpts.queryKey]);

  const handleManualRefresh = useCallback(async () => {
    setIsSyncing(true);
    try {
      await invalidate();
    } finally {
      setIsSyncing(false);
    }
  }, [invalidate]);

  // --- Effects ---

  // Re-fetch strategies when draft strategy changes (local DB only).
  useEffect(() => {
    if (draftStrategy) {
      void queryClient.invalidateQueries({ queryKey: listOpts.queryKey });
      void queryClient.invalidateQueries({ queryKey: dismissedOpts.queryKey });
    }
  }, [draftStrategy, queryClient, listOpts.queryKey, dismissedOpts.queryKey]);

  return {
    strategies,
    dismissedStrategies,
    isLoading: strategiesQuery.isLoading,
    isFetched: strategiesQuery.isFetched,
    isSyncing,
    invalidate,
    handleManualRefresh,
  };
}
