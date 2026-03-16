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
  Message,
  OptimizationProgressData,
  PlanningArtifact,
  Step,
  Strategy,
  ToolCall,
} from "@pathfinder/shared";
import type { ChatSSEEvent } from "@/lib/sse_events";
import { handleChatEvent } from "@/features/chat/handlers/handleChatEvent";
import type { ChatEventContext } from "@/features/chat/handlers/handleChatEvent";
import { snapshotSubKaniActivityFromBuffers } from "@/features/chat/handlers/handleChatEvent.messageEvents";
import { useSessionStore } from "@/state/useSessionStore";
import type { GraphSnapshotInput } from "@/features/chat/utils/graphSnapshot";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import type { StreamSessionState } from "@/features/chat/handlers/handleChatEvent.types";

type Thinking = ReturnType<typeof useThinkingState>;
type AddStrategyInput = Parameters<ChatEventContext["addStrategy"]>[0];

export interface StreamEventDeps {
  siteId: string;
  thinking: Thinking;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  setUndoSnapshots: React.Dispatch<React.SetStateAction<Record<number, Strategy>>>;
  setStrategyId: (id: string | null) => void;
  addStrategy: (strategy: AddStrategyInput) => void;
  addExecutedStrategy: (strategy: Strategy) => void;
  setWdkInfo: ChatEventContext["setWdkInfo"];
  setStrategy: (strategy: Strategy | null) => void;
  setStrategyMeta: ChatEventContext["setStrategyMeta"];
  clearStrategy: () => void;
  addStep: (step: Step) => void;
  loadGraph: (graphId: string) => void;
  currentStrategy: Strategy | null;
  parseToolArguments: ChatEventContext["parseToolArguments"];
  parseToolResult: ChatEventContext["parseToolResult"];
  applyGraphSnapshot: (graphSnapshot: GraphSnapshotInput) => void;
  getStrategy: (id: string) => Promise<Strategy>;
  attachThinkingToLastAssistant: (
    calls: ToolCall[],
    activity?: { calls: Record<string, ToolCall[]>; status: Record<string, string> },
  ) => void;
  setSelectedModelId?: (modelId: string | null) => void;
  setOptimizationProgress: React.Dispatch<
    React.SetStateAction<OptimizationProgressData | null>
  >;
  onApiError?: (message: string) => void;
  onWorkbenchGeneSet?: ChatEventContext["onWorkbenchGeneSet"];
}

export interface StreamEventCallbacks {
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
      const subKaniTokenUsageBuffer: Record<
        string,
        import("@pathfinder/shared").SubKaniTokenUsage
      > = {};

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
        setSelectedModelId,
        onApiError,
        onWorkbenchGeneSet,
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

          // Persist reasoning to the last assistant message.
          const savedReasoning = streamState.reasoning;
          if (savedReasoning) {
            setMessages((prev) => {
              for (let i = prev.length - 1; i >= 0; i -= 1) {
                if (prev[i].role !== "assistant") continue;
                const msg = prev[i];
                if (msg.reasoning) return prev;
                const next = [...prev];
                next[i] = { ...msg, reasoning: savedReasoning };
                return next;
              }
              return prev;
            });
          }

          // Force-write optimization data to the last assistant message.
          const savedOptimization = streamState.optimizationProgress;
          if (savedOptimization) {
            setMessages((prev) => {
              for (let i = prev.length - 1; i >= 0; i -= 1) {
                if (prev[i].role !== "assistant") continue;
                const next = [...prev];
                next[i] = {
                  ...prev[i],
                  optimizationProgress: savedOptimization,
                };
                return next;
              }
              return prev;
            });
          }

          // Refresh strategy from server if no snapshot was applied.
          if (effectiveStrategyId && !session.snapshotApplied) {
            getStrategy(effectiveStrategyId)
              .then((full) => {
                const currentId = useSessionStore.getState().strategyId;
                if (currentId !== effectiveStrategyId) return;
                setStrategy(full);
                setStrategyMeta({
                  name: full.name,
                  recordType: full.recordType ?? undefined,
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
