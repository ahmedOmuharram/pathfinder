"use client";

import { queryOptions, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ConversationResponse, Strategy } from "@pathfinder/shared";
import { getStrategy } from "@pathfinder/shared/generated/hooks/useGetStrategy";

import { APIError } from "./http";

export function toStrategy(response: ConversationResponse): Strategy {
  return {
    ...response,
    steps: response.steps ?? [],
    rootStepId: response.rootStepId ?? null,
    recordType: response.recordType ?? null,
    isSaved: response.isSaved ?? false,
  };
}

export function strategyQueryKey(conversationId: string) {
  return ["conversations", conversationId, "detail"] as const;
}

async function fetchStrategy(conversationId: string): Promise<Strategy | null> {
  try {
    const raw = await getStrategy(conversationId);
    return toStrategy(raw);
  } catch (err) {
    if (err instanceof APIError && err.status === 404) return null;
    throw err;
  }
}

export function strategyQueryOptions(conversationId: string) {
  return queryOptions({
    queryKey: strategyQueryKey(conversationId),
    queryFn: () => fetchStrategy(conversationId),
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

export function useStrategyQuery(conversationId: string) {
  return useQuery(strategyQueryOptions(conversationId));
}

export function useStrategyData(conversationId: string): Strategy | null {
  const { data } = useStrategyQuery(conversationId);
  return data ?? null;
}

export function useStrategyCacheUtils() {
  const client = useQueryClient();
  return {
    get: (id: string): Strategy | null =>
      client.getQueryData<Strategy>(strategyQueryKey(id)) ?? null,
    set: (id: string, next: Strategy | null) =>
      client.setQueryData<Strategy | null>(strategyQueryKey(id), next),
  };
}
