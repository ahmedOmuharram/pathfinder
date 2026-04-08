"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { openStrategy, strategiesListOptions } from "@/lib/api/strategies";
import { DEFAULT_STREAM_NAME, type Strategy } from "@pathfinder/shared";
import { useSessionStore } from "@/state/useSessionStore";
import { resolveActiveConversation } from "@/features/sidebar/utils/resolveActiveConversation";

interface UseAutoConversationArgs {
  siteId: string;
  strategyItems: Strategy[];
  isFetched: boolean;
}

export interface AutoConversationResult {
  setNewConversationInFlight: (inFlight: boolean) => void;
}

export function useAutoConversation({
  siteId,
  strategyItems,
  isFetched,
}: UseAutoConversationArgs): AutoConversationResult {
  const strategyId = useSessionStore((s) => s.strategyId);
  const setStrategyId = useSessionStore((s) => s.setStrategyId);
  const veupathdbSignedIn = useSessionStore((s) => s.veupathdbSignedIn);
  const chatIsStreaming = useSessionStore((s) => s.chatIsStreaming);
  const queryClient = useQueryClient();

  const [newConversationInFlight, setNewConversationInFlight] = useState(false);
  const listKey = strategiesListOptions(siteId).queryKey;

  const action = (newConversationInFlight || chatIsStreaming)
    ? { type: "keep" as const }
    : resolveActiveConversation({
        strategyId,
        hasAuth: veupathdbSignedIn,
        strategyItems,
        hasFetched: isFetched,
      });

  useQuery({
    queryKey: ["auto-pick-conversation", action.type === "pick" ? action.strategyId : null] as const,
    queryFn: () => {
      if (action.type === "pick") {
        setStrategyId(action.strategyId);
      }
      return { picked: true };
    },
    enabled: action.type === "pick",
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
  });

  useQuery({
    queryKey: ["auto-create-conversation", siteId, action.type] as const,
    queryFn: async () => {
      const res = await openStrategy({ siteId });
      const now = new Date().toISOString();
      queryClient.setQueryData<Strategy[]>(
        listKey,
        (old) => [
          ...(old ?? []),
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
        ],
      );
      const currentId = useSessionStore.getState().strategyId;
      if (currentId == null || currentId === "") {
        setStrategyId(res.strategyId);
      }
      void queryClient.invalidateQueries({ queryKey: listKey });
      return res;
    },
    enabled: action.type === "create",
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
  });

  return { setNewConversationInFlight };
}
