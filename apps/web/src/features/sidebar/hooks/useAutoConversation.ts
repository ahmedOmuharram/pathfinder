"use client";

/**
 * Auto-conversation selection / creation for the conversation sidebar.
 *
 * Ensures there is always an active conversation selected. When no
 * strategy is active, picks the most recent one or creates a new one.
 *
 * Uses useQueryClient() directly for optimistic cache updates.
 */

import { useCallback, useEffect, useRef, startTransition } from "react";
import { useQueryClient } from "@tanstack/react-query";
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
  /** Signal that a new conversation POST is in flight. */
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

  const autoCreateInFlight = useRef(false);
  const newConversationInFlight = useRef(false);
  const prevSiteRef = useRef(siteId);

  const listKey = strategiesListOptions(siteId).queryKey;

  // Reset auto-create guard on site change.
  useEffect(() => {
    if (prevSiteRef.current !== siteId) {
      prevSiteRef.current = siteId;
      autoCreateInFlight.current = false;
    }
  }, [siteId]);

  const ensureActiveConversation = useCallback(async () => {
    // Don't auto-pick while the user is explicitly creating a new conversation
    // or while chat is streaming (the chat flow creates its own conversation).
    if (newConversationInFlight.current || chatIsStreaming) return;

    const action = resolveActiveConversation({
      strategyId,
      hasAuth: veupathdbSignedIn,
      strategyItems,
      hasFetched: isFetched,
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
    queryClient,
    isFetched,
    listKey,
  ]);

  // Ensure there's always an active conversation selected.
  useEffect(() => {
    startTransition(() => {
      void ensureActiveConversation();
    });
  }, [ensureActiveConversation]);

  const setNewConversationInFlight = useCallback((inFlight: boolean) => {
    newConversationInFlight.current = inFlight;
  }, []);

  return { setNewConversationInFlight };
}
