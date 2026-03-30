/**
 * Stream event wiring -- builds the onMessage / onComplete / onError
 * callbacks consumed by ``streamChat``.
 *
 * This hook is a pure callback factory: it creates fresh event buffers
 * on each call and returns the three callbacks that ``streamChat`` needs.
 */

import { useCallback } from "react";
import type {
  Citation,
  OptimizationProgressData,
  PlanningArtifact,
  SubKaniTokenUsage,
  ToolCall,
} from "@pathfinder/shared";
import type { ChatSSEEvent } from "@/lib/sse_events";
import { handleChatEvent } from "@/features/chat/handlers/handleChatEvent";
import type { ChatEventContext } from "@/features/chat/handlers/handleChatEvent";
import { snapshotSubKaniActivityFromBuffers } from "@/features/chat/handlers/handleChatEvent.messageEvents";
import { useSessionStore } from "@/state/useSessionStore";
import {
  persistReasoningToLastMessage,
  persistOptimizationDataToLastMessage,
} from "@/features/chat/hooks/streamCompletionHelpers";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import type { StreamSessionState } from "@/features/chat/handlers/handleChatEvent.types";
import type { StreamEventDepsGroup } from "@/features/chat/hooks/useChatStreaming";

interface StreamEventDeps extends StreamEventDepsGroup {
  setOptimizationProgress: React.Dispatch<
    React.SetStateAction<OptimizationProgressData | null>
  >;
}

interface StreamEventCallbacks {
  onMessage: (event: ChatSSEEvent) => void;
  onComplete: () => void;
  onError: (error: Error) => void;
  /** The mutable tool-call buffer, needed by the lifecycle layer for finalization. */
  toolCalls: ToolCall[];
}

/**
 * Returns a factory that, given a session and strategy context, produces
 * fresh event buffers and the three stream callbacks.
 */
export function useStreamEvents(deps: StreamEventDeps) {
  const {
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
    setSelectedModelId,
    setOptimizationProgress,
    onApiError,
    onWorkbenchGeneSet,
  } = deps;

  /**
   * Build fresh per-stream event buffers and callbacks.
   *
   * Called once at the start of each ``executeStream`` invocation so
   * every stream gets its own isolated mutable state.
   */
  const buildStreamCallbacks = useCallback(
    (
      session: StreamingSession,
      effectiveStrategyId: string | null,
      onFinalize: (toolCalls: ToolCall[]) => void,
      onError: (error: Error, toolCalls: ToolCall[]) => void,
    ): StreamEventCallbacks => {
      const toolCalls: ToolCall[] = [];
      const citationsBuffer: Citation[] = [];
      const planningArtifactsBuffer: PlanningArtifact[] = [];
      const subKaniCallsBuffer: Record<string, ToolCall[]> = {};
      const subKaniStatusBuffer: Record<string, string> = {};
      const subKaniModelsBuffer: Record<string, string> = {};
      const subKaniTokenUsageBuffer: Record<string, SubKaniTokenUsage> = {};

      const streamState: StreamSessionState = {
        streamingAssistantIndex: null,
        streamingAssistantMessageId: null,
        turnAssistantIndex: null,
        reasoning: null,
        optimizationProgress: null,
      };

      const ctx: ChatEventContext = {
        siteId,
        strategyIdAtStart: effectiveStrategyId,
        toolCallsBuffer: toolCalls,
        citationsBuffer,
        planningArtifactsBuffer,
        subKaniCallsBuffer,
        subKaniStatusBuffer,
        subKaniModelsBuffer,
        subKaniTokenUsageBuffer,
        thinking,
        setStrategyId,
        addStrategy,
        addExecutedStrategy,
        setWdkInfo,
        setStrategy,
        setStrategyMeta,
        clearStrategy,
        addStep,
        loadGraph,
        session,
        currentStrategy,
        setMessages,
        setUndoSnapshots,
        parseToolArguments,
        parseToolResult,
        applyGraphSnapshot,
        getStrategy,
        streamState,
        setOptimizationProgress,
        ...(setSelectedModelId != null ? { setSelectedModelId } : {}),
        ...(onApiError != null ? { onApiError } : {}),
        ...(onWorkbenchGeneSet != null ? { onWorkbenchGeneSet } : {}),
      };

      return {
        toolCalls,

        onMessage: (event: ChatSSEEvent) => {
          handleChatEvent(ctx, event);
        },

        onComplete: () => {
          onFinalize(toolCalls);

          const subKaniActivity = snapshotSubKaniActivityFromBuffers(
            subKaniCallsBuffer,
            subKaniStatusBuffer,
            subKaniModelsBuffer,
            subKaniTokenUsageBuffer,
          );
          attachThinkingToLastAssistant(
            toolCalls.length > 0 ? [...toolCalls] : [],
            subKaniActivity,
          );

          // Persist buffered reasoning & optimization data to messages.
          setMessages((prev) =>
            persistOptimizationDataToLastMessage(
              persistReasoningToLastMessage(prev, streamState.reasoning),
              streamState.optimizationProgress,
            ),
          );

          // Refresh strategy from server if no snapshot was applied.
          if (
            effectiveStrategyId != null &&
            effectiveStrategyId !== "" &&
            !session.snapshotApplied
          ) {
            getStrategy(effectiveStrategyId)
              .then((full) => {
                const currentId = useSessionStore.getState().strategyId;
                if (currentId !== effectiveStrategyId) return;
                setStrategy(full);
                setStrategyMeta({
                  name: full.name,
                  ...(full.recordType != null ? { recordType: full.recordType } : {}),
                  siteId: full.siteId,
                });
              })
              .catch((err) =>
                console.error(
                  "[useChatStreaming] Failed to refresh strategy after stream:",
                  err,
                ),
              );
          }
        },

        onError: (error: Error) => {
          onError(error, toolCalls);
        },
      };
    },
    [
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
      setSelectedModelId,
      setOptimizationProgress,
      onApiError,
      onWorkbenchGeneSet,
    ],
  );

  return { buildStreamCallbacks };
}
