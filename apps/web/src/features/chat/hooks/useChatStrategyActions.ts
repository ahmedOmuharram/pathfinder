"use client";

import { useCallback, useRef, type MutableRefObject } from "react";
import type { Message, ToolCall } from "@pathfinder/shared";
import { getStrategy } from "@/lib/api/strategies";
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
  sessionRef: MutableRefObject<StreamingSession | null>,
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>,
) {
  // --- Strategy store selectors ---
  const addStep = useStrategyStore((s) => s.addStep);
  const setStrategy = useStrategyStore((s) => s.setStrategy);
  const setWdkInfo = useStrategyStore((s) => s.setWdkInfo);
  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);
  const clearStrategy = useStrategyStore((s) => s.clear);
  const stepsById = useStrategyStore((s) => s.stepsById);
  const addStrategy = useStrategyStore((s) => s.addStrategyToList);
  const addExecutedStrategy = useStrategyStore((s) => s.addExecutedStrategy);

  // --- Load graph from API ---
  // Cancellation guard: each call invalidates the previous in-flight request
  // so stale responses from earlier graphIds are silently dropped.
  const loadGraphCancelRef = useRef(0);

  const loadGraph = useCallback(
    (graphId: string) => {
      if (graphId === "") return;
      const token = ++loadGraphCancelRef.current;
      getStrategy(graphId)
        .then((full) => {
          if (token !== loadGraphCancelRef.current) return;
          if (sessionRef.current?.snapshotApplied) return;
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
    },
    [setStrategy, setStrategyMeta, sessionRef],
  );

  // --- Attach thinking metadata to last assistant message ---
  const handleAttachThinking = useCallback(
    (calls: ToolCall[]) => {
      setMessages((prev) => attachThinkingToLastAssistant(prev, calls));
    },
    [setMessages],
  );

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
