"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { strategiesListOptions, dismissedStrategiesOptions } from "@/lib/api/strategies";
import type { Strategy } from "@pathfinder/shared";
import { useSessionStore } from "@/state/useSessionStore";

interface UseStrategyFetchingArgs {
  siteId: string;
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
}: UseStrategyFetchingArgs): StrategyFetchingResult {
  const veupathdbSignedIn = useSessionStore((s) => s.veupathdbSignedIn);
  const authStatusKnown = useSessionStore((s) => s.authStatusKnown);
  const authRefreshed = useSessionStore((s) => s.authRefreshed);
  const queryClient = useQueryClient();

  const [isSyncing, setIsSyncing] = useState(false);

  const queryEnabled = authStatusKnown && veupathdbSignedIn && authRefreshed && siteId !== "";

  const listOpts = strategiesListOptions(siteId);
  const dismissedOpts = dismissedStrategiesOptions(siteId);

  const strategiesQuery = useQuery({ ...listOpts, enabled: queryEnabled });
  const dismissedQuery = useQuery({ ...dismissedOpts, enabled: queryEnabled });

  const strategies: Strategy[] = strategiesQuery.data ?? [];
  const dismissedStrategies: Strategy[] = dismissedQuery.data ?? [];

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: listOpts.queryKey }),
      queryClient.invalidateQueries({ queryKey: dismissedOpts.queryKey }),
    ]);
  };

  const handleManualRefresh = async () => {
    setIsSyncing(true);
    try {
      await invalidate();
    } finally {
      setIsSyncing(false);
    }
  };

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
