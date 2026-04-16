"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  chatListOptions,
  dismissedChatsOptions,
  type ChatListItem,
} from "@/lib/api/chats";
import { useSessionStore } from "@/state/useSessionStore";

interface UseChatListFetchingArgs {
  siteId: string;
}

export interface ChatListFetchingResult {
  chats: ChatListItem[];
  dismissedChats: ChatListItem[];
  isLoading: boolean;
  isFetched: boolean;
  isSyncing: boolean;
  invalidate: () => Promise<void>;
  handleManualRefresh: () => Promise<void>;
}

export function useChatListFetching({
  siteId,
}: UseChatListFetchingArgs): ChatListFetchingResult {
  const authStatusKnown = useSessionStore((s) => s.authStatusKnown);
  const authRefreshed = useSessionStore((s) => s.authRefreshed);
  const queryClient = useQueryClient();

  const [isSyncing, setIsSyncing] = useState(false);

  const queryEnabled = authStatusKnown && authRefreshed && siteId !== "";

  const listOpts = chatListOptions(siteId);
  const dismissedOpts = dismissedChatsOptions(siteId);

  const listQuery = useQuery({ ...listOpts, enabled: queryEnabled });
  const dismissedQuery = useQuery({ ...dismissedOpts, enabled: queryEnabled });

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
    chats: listQuery.data ?? [],
    dismissedChats: dismissedQuery.data ?? [],
    isLoading: listQuery.isLoading,
    isFetched: listQuery.isFetched,
    isSyncing,
    invalidate,
    handleManualRefresh,
  };
}
