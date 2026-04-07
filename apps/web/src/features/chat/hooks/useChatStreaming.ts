import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type {
  ChatMention,
  UserMessage,
  ToolCall,
  ModelSelection,
  Strategy,
} from "@pathfinder/shared";
import type { NodeSelection } from "@/lib/types/nodeSelection";
import { streamChat } from "@/features/chat/stream";
import { useSettingsStore } from "@/state/useSettingsStore";
import { encodeNodeSelection } from "@/features/chat/node_selection";
import { strategiesListOptions } from "@/lib/api/strategies";
import { queryKeyPrefixes } from "@/lib/query/keys";
import type {
  StrategyActions,
  UISetters,
  EventHelpers,
  OptionalCallbacks,
} from "@/features/chat/handlers/handleChatEvent";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import { useStreamLifecycle } from "@/features/chat/hooks/useStreamLifecycle";
import { useStreamEvents } from "@/features/chat/hooks/useStreamEvents";

type Thinking = ReturnType<typeof useThinkingState>;

/** Event-handling dependencies passed through to useStreamEvents. */
export interface StreamEventDepsGroup extends
  StrategyActions,
  Omit<UISetters, "setOptimizationProgress">,
  EventHelpers,
  OptionalCallbacks {
  siteId: string;
  thinking: Thinking;
  currentStrategy: Strategy | null;
  attachThinkingToLastAssistant: (
    calls: ToolCall[],
    activity?: { calls: Record<string, ToolCall[]>; status: Record<string, string> },
  ) => void;
}

interface UseChatStreamingArgs extends StreamEventDepsGroup {
  strategyId: string | null;
  draftSelection: NodeSelection | null;
  setDraftSelection: (selection: NodeSelection | null) => void;
  sessionRef: { current: StreamingSession | null };
  createSession: () => StreamingSession;
  modelSelection?: ModelSelection | null;
  onStreamComplete?: () => void;
  onStreamError?: (error: Error) => void;
  setChatIsStreaming?: (streaming: boolean) => void;
}

export function useChatStreaming({
  siteId,
  strategyId,
  draftSelection,
  setDraftSelection,
  thinking,
  setMessages,
  setUndoSnapshots,
  sessionRef,
  createSession,
  loadGraph,
  addStrategy,
  addExecutedStrategy,
  setStrategyId,
  setWdkInfo,
  setStrategy,
  setStrategyMeta,
  clearStrategy,
  addStep,
  parseToolArguments,
  parseToolResult,
  applyGraphSnapshot,
  getStrategy,
  currentStrategy,
  attachThinkingToLastAssistant,
  setSelectedModelId,
  modelSelection,
  onApiError,
  onWorkbenchGeneSet,
  onStreamComplete,
  onStreamError,
  setChatIsStreaming,
}: UseChatStreamingArgs) {
  // --- Sub-hooks ---
  const queryClient = useQueryClient();
  const lifecycle = useStreamLifecycle(thinking, setChatIsStreaming);
  const { buildStreamCallbacks } = useStreamEvents({
    siteId,
    thinking,
    setMessages,
    setUndoSnapshots,
    setStrategyId,
    addStrategy,
    addExecutedStrategy,
    setWdkInfo,
    setStrategy,
    setStrategyMeta,
    clearStrategy,
    addStep,
    loadGraph,
    currentStrategy,
    parseToolArguments,
    parseToolResult,
    applyGraphSnapshot,
    getStrategy,
    attachThinkingToLastAssistant,
    ...(setSelectedModelId != null ? { setSelectedModelId } : {}),
    setOptimizationProgress: lifecycle.setOptimizationProgress,
    ...(onApiError != null ? { onApiError } : {}),
    ...(onWorkbenchGeneSet != null ? { onWorkbenchGeneSet } : {}),
  });

  // --- Core stream execution ---
  const executeStream = useCallback(
    async (
      content: string,
      streamContext: { strategyId?: string; mentions?: ChatMention[]; metadata?: Record<string, unknown> },
    ): Promise<string | null> => {
      lifecycle.beginStream();

      const session = createSession();
      sessionRef.current = session;

      const effectiveStrategyId = streamContext.strategyId ?? strategyId;

      const callbacks = buildStreamCallbacks(
        session,
        effectiveStrategyId ?? null,
        (toolCalls: ToolCall[]) => {
          lifecycle.finalizeStream(toolCalls);
          void queryClient.invalidateQueries({ queryKey: strategiesListOptions(siteId).queryKey });
          if (effectiveStrategyId != null && effectiveStrategyId !== "") {
            void queryClient.invalidateQueries({ queryKey: queryKeyPrefixes.strategies });
          }
          onStreamComplete?.();
        },
        (error: Error, toolCalls: ToolCall[]) => {
          lifecycle.handleStreamError(error, toolCalls, onStreamError);
          void queryClient.invalidateQueries({ queryKey: strategiesListOptions(siteId).queryKey });
          if (effectiveStrategyId != null && effectiveStrategyId !== "") {
            void queryClient.invalidateQueries({ queryKey: queryKeyPrefixes.strategies });
          }
        },
      );

      try {
        const { disabledTools } = useSettingsStore.getState();
        const result = await streamChat(
          content,
          siteId,
          {
            onMessage: callbacks.onMessage,
            onComplete: callbacks.onComplete,
            onError: callbacks.onError,
          },
          streamContext,
          undefined,
          modelSelection ?? undefined,
          disabledTools.length > 0 ? disabledTools : undefined,
        );

        lifecycle.trackOperation(result.subscription, result.operationId);

        if (streamContext.strategyId == null && result.strategyId !== "") {
          setStrategyId(result.strategyId);
        }
        return result.entryId;
      } catch (e) {
        const error = e instanceof Error ? e : new Error(String(e));
        lifecycle.handleStreamError(error, callbacks.toolCalls, onStreamError);
        return null;
      }
    },
    [
      lifecycle,
      createSession,
      sessionRef,
      strategyId,
      buildStreamCallbacks,
      siteId,
      queryClient,
      modelSelection,
      setStrategyId,
      onStreamComplete,
      onStreamError,
    ],
  );

  // --- Public API ---
  const handleSendMessage = useCallback(
    async (content: string, mentions?: ChatMention[], metadata?: Record<string, unknown>) => {
      const finalContent = encodeNodeSelection(draftSelection, content);
      const userMessage: UserMessage = {
        role: "user",
        content: finalContent,
        ...(mentions != null && mentions.length > 0 ? { mentions } : {}),
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);
      if (draftSelection) {
        setDraftSelection(null);
      }

      const entryId = await executeStream(finalContent, {
        ...(strategyId != null ? { strategyId } : {}),
        ...(mentions != null ? { mentions } : {}),
        ...(metadata != null ? { metadata } : {}),
      });
      // Attach the Redis entry ID to the user message for undo support.
      if (entryId != null && entryId !== "") {
        setMessages((prev) => {
          let last = -1;
          for (let i = prev.length - 1; i >= 0; i--) {
            if (prev[i]?.role === "user") { last = i; break; }
          }
          const existing = last >= 0 ? prev[last] : undefined;
          if (existing?.role !== "user") return prev;
          const patched: UserMessage = { ...existing, entryId };
          const updated = [...prev];
          updated[last] = patched;
          return updated;
        });
      }
    },
    [draftSelection, setMessages, setDraftSelection, strategyId, executeStream],
  );

  const handleAutoExecute = useCallback(
    async (prompt: string, targetStrategyId: string) => {
      await executeStream(prompt, { strategyId: targetStrategyId });
    },
    [executeStream],
  );

  return {
    handleSendMessage,
    handleAutoExecute,
    stopStreaming: lifecycle.stopStreaming,
    isStreaming: lifecycle.isStreaming,
    apiError: lifecycle.apiError,
    setIsStreaming: lifecycle.setIsStreaming,
    optimizationProgress: lifecycle.optimizationProgress,
    setOptimizationProgress: lifecycle.setOptimizationProgress,
  };
}
