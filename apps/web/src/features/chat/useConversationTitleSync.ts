"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import type { PathfinderUIMessage, Strategy } from "@pathfinder/shared";

import { strategiesListOptions } from "@/lib/api/strategies";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/strategy/store";

export function useConversationTitleSync({
  chatId,
  messages,
  siteId,
}: {
  chatId: string;
  messages: PathfinderUIMessage[];
  siteId: string;
}): void {
  const queryClient = useQueryClient();
  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);
  const currentStrategyId = useSessionStore((s) => s.strategyId);

  const [lastSyncedTitle, setLastSyncedTitle] = useState<string | null>(null);

  const incomingTitle = extractLatestTitle(messages);

  if (
    chatId !== "" &&
    incomingTitle !== null &&
    incomingTitle !== lastSyncedTitle
  ) {
    setLastSyncedTitle(incomingTitle);

    const listKey = strategiesListOptions(siteId).queryKey;
    const now = new Date().toISOString();
    queryClient.setQueryData<Strategy[]>(listKey, (old) => {
      const existing = (old ?? []).find((s) => s.id === chatId);
      const merged: Strategy = existing
        ? { ...existing, name: incomingTitle, updatedAt: now }
        : {
            id: chatId,
            name: incomingTitle,
            updatedAt: now,
            createdAt: now,
            siteId,
            recordType: null,
            steps: [],
            rootStepId: null,
            stepCount: 0,
            isSaved: false,
          };
      const rest = (old ?? []).filter((s) => s.id !== chatId);
      return [merged, ...rest];
    });
    void queryClient.invalidateQueries({ queryKey: listKey });

    if (currentStrategyId === chatId) {
      setStrategyMeta({ name: incomingTitle });
    }
  }
}

function extractLatestTitle(messages: PathfinderUIMessage[]): string | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (message === undefined) continue;
    if (message.role !== "assistant") continue;
    const title = message.metadata?.conversationTitle;
    if (typeof title === "string" && title.length > 0) {
      return title;
    }
  }
  return null;
}
