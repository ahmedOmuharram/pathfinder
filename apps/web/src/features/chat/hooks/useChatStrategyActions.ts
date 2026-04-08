"use client";

import { useRef, type RefObject } from "react";
import type { Message, ToolCall } from "@pathfinder/shared";
import { useShallow } from "zustand/react/shallow";
import { getStrategy } from "@/lib/api/strategies";
import { addStrategyToCache } from "@/lib/query/mutations/addStrategyToCache";
import { useStrategyStore } from "@/state/strategy/store";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import { attachThinkingToLastAssistant } from "@/features/chat/utils/attachThinkingToLastAssistant";

/**
 * Strategy store selectors and strategy-related callbacks used by UnifiedChatPanel.
 *
 * Groups all strategy store reads together with `loadGraph` (fetches a full
 * strategy from the API) and `handleAttachThinking` (attaches tool-call
 * metadata to the last assistant message).
 */
export function useChatStrategyActions(
  sessionRef: RefObject<StreamingSession | null>,
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>,
) {
  // --- Strategy store selectors ---
  const {
    addStep,
    setStrategy,
    setWdkInfo,
    setStrategyMeta,
    clear: clearStrategy,
    stepsById,
    addExecutedStrategy,
  } = useStrategyStore(
    useShallow((s) => ({
      addStep: s.addStep,
      setStrategy: s.setStrategy,
      setWdkInfo: s.setWdkInfo,
      setStrategyMeta: s.setStrategyMeta,
      clear: s.clear,
      stepsById: s.stepsById,
      addExecutedStrategy: s.addExecutedStrategy,
    })),
  );
  const addStrategy = addStrategyToCache;

  // --- Load graph from API ---
  // Cancellation guard: each call invalidates the previous in-flight request
  // so stale responses from earlier graphIds are silently dropped.
  const loadGraphCancelRef = useRef(0);

  const loadGraph = (graphId: string) => {
    if (graphId === "") return;
    const token = ++loadGraphCancelRef.current;
    getStrategy(graphId)
      .then((full) => {
        if (token !== loadGraphCancelRef.current) return;
        if (sessionRef.current?.snapshotApplied === true) return;
        setStrategy(full);
        setStrategyMeta({
          name: full.name,
          ...(full.recordType != null ? { recordType: full.recordType } : {}),
          siteId: full.siteId,
        });
      })
      .catch((err) => {
        if (token !== loadGraphCancelRef.current) return;
        console.warn("[UnifiedChat] Failed to load graph:", err);
      });
  };

  // --- Attach thinking metadata to last assistant message ---
  const handleAttachThinking = (calls: ToolCall[]) => {
    setMessages((prev) => attachThinkingToLastAssistant(prev, calls));
  };

  return {
    addStep,
    setStrategy,
    setWdkInfo,
    setStrategyMeta,
    clearStrategy,
    stepsById,
    addStrategy,
    addExecutedStrategy,
    loadGraph,
    handleAttachThinking,
  };
}
