"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Strategy } from "@pathfinder/shared";
import { conversationDetailKey, conversationDetailOptions } from "@/lib/api/conversations";

export function useStrategyQuery(conversationId: string) {
  return useQuery(conversationDetailOptions(conversationId));
}

export function useStrategyData(conversationId: string): Strategy | null {
  const { data } = useStrategyQuery(conversationId);
  return data ?? null;
}

export function useStrategyCacheUtils() {
  const client = useQueryClient();
  return {
    get: (id: string): Strategy | null =>
      client.getQueryData<Strategy>(conversationDetailKey(id)) ?? null,
    set: (id: string, next: Strategy | null) =>
      client.setQueryData<Strategy | null>(conversationDetailKey(id), next),
  };
}
