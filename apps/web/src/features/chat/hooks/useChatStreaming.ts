import { useCallback, useState } from "react";
import type {
  Message,
  ToolCall,
  ChatMode,
  Citation,
  ModelSelection,
  PlanningArtifact,
  OptimizationProgressData,
} from "@pathfinder/shared";
import type { ChatSSEEvent } from "@/features/chat/sse_events";
import { streamChat } from "@/features/chat/stream";
import { handleChatEvent } from "@/features/chat/handlers/handleChatEvent";
import type { ChatEventContext } from "@/features/chat/handlers/handleChatEvent";
import { snapshotSubKaniActivityFromBuffers } from "@/features/chat/handlers/handleChatEvent.messageEvents";
import { encodeNodeSelection } from "@/features/chat/node_selection";
import type { StrategyStep, StrategyWithMeta } from "@/types/strategy";
import type { GraphSnapshotInput } from "@/features/chat/utils/graphSnapshot";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";

type Thinking = ReturnType<typeof useThinkingState>;
type AddStrategyInput = Parameters<ChatEventContext["addStrategy"]>[0];

interface UseChatStreamingArgs {
  siteId: string;
  strategyId: string | null;
  /** Plan session id – passed to streamChat for plan mode. */
  planSessionId?: string | null;
  draftSelection: Record<string, unknown> | null;
  setDraftSelection: (selection: Record<string, unknown> | null) => void;
  thinking: Thinking;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  setUndoSnapshots: React.Dispatch<
    React.SetStateAction<Record<number, StrategyWithMeta>>
  >;
  sessionRef: { current: StreamingSession | null };
  createSession: () => StreamingSession;
  loadGraph: (graphId: string) => void;
  addStrategy: (strategy: AddStrategyInput) => void;
  addExecutedStrategy: (strategy: StrategyWithMeta) => void;
  setStrategyId: (id: string | null) => void;
  setWdkInfo: ChatEventContext["setWdkInfo"];
  setStrategy: (strategy: StrategyWithMeta | null) => void;
  setStrategyMeta: ChatEventContext["setStrategyMeta"];
  clearStrategy: () => void;
  addStep: (step: StrategyStep) => void;
  parseToolArguments: ChatEventContext["parseToolArguments"];
  parseToolResult: ChatEventContext["parseToolResult"];
  applyGraphSnapshot: (graphSnapshot: GraphSnapshotInput) => void;
  getStrategy: (id: string) => Promise<StrategyWithMeta>;
  currentStrategy: StrategyWithMeta | null;
  attachThinkingToLastAssistant: (
    calls: ToolCall[],
    activity?: { calls: Record<string, ToolCall[]>; status: Record<string, string> },
  ) => void;
  mode?: ChatMode;
  /** Per-request model/provider/reasoning selection. */
  modelSelection?: ModelSelection | null;
  /** Reference strategy ID to inject into plan-mode context. */
  referenceStrategyId?: string | null;

  /** Optional conversation callbacks. */
  onPlanSessionId?: (id: string) => void;
  onPlanningArtifactUpdate?: (artifact: PlanningArtifact) => void;
  onExecutorBuildRequest?: (message: string) => void;
  onConversationTitleUpdate?: (title: string) => void;
  onApiError?: (message: string) => void;
  /** Called after streaming completes successfully. */
  onStreamComplete?: () => void;
  /** Called after streaming errors out (in addition to the default error handling). */
  onStreamError?: (error: Error) => void;
}

export function useChatStreaming({
  siteId,
  strategyId,
  planSessionId,
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
  mode = "execute",
  modelSelection,
  referenceStrategyId,
  onPlanSessionId,
  onPlanningArtifactUpdate,
  onExecutorBuildRequest,
  onConversationTitleUpdate,
  onApiError,
  onStreamComplete,
  onStreamError,
}: UseChatStreamingArgs) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [optimizationProgress, setOptimizationProgress] =
    useState<OptimizationProgressData | null>(null);
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  const stopStreaming = useCallback(() => {
    abortController?.abort();
    setAbortController(null);
  }, [abortController]);

  /**
   * Shared stream setup — resets state, wires event handling, and calls
   * ``streamChat``.  Used by both ``handleSendMessage`` (user-initiated)
   * and ``handleAutoExecute`` (system-initiated, no visible user message).
   */
  const executeStream = useCallback(
    async (
      content: string,
      streamMode: "execute" | "plan",
      streamContext: {
        strategyId?: string;
        planSessionId?: string;
        referenceStrategyId?: string;
      },
    ) => {
      setIsStreaming(true);
      setApiError(null);
      thinking.reset();
      setOptimizationProgress(null);

      const session = createSession();
      sessionRef.current = session;

      const streamState: ChatEventContext["streamState"] = {
        streamingAssistantIndex: null,
        streamingAssistantMessageId: null,
        turnAssistantIndex: null,
        reasoning: null,
        optimizationProgress: null,
      };

      const toolCalls: ToolCall[] = [];
      const citationsBuffer: Citation[] = [];
      const planningArtifactsBuffer: PlanningArtifact[] = [];
      const subKaniCallsBuffer: Record<string, ToolCall[]> = {};
      const subKaniStatusBuffer: Record<string, string> = {};

      const controller = new AbortController();
      setAbortController(controller);

      const effectiveStrategyId = streamContext.strategyId ?? strategyId;

      await streamChat(
        content,
        siteId,
        {
          onMessage: (event: ChatSSEEvent) => {
            handleChatEvent(
              {
                siteId,
                strategyIdAtStart: effectiveStrategyId ?? null,
                toolCallsBuffer: toolCalls,
                citationsBuffer,
                planningArtifactsBuffer,
                subKaniCallsBuffer,
                subKaniStatusBuffer,
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
                onPlanSessionId,
                onPlanningArtifactUpdate,
                onExecutorBuildRequest,
                onConversationTitleUpdate,
                onApiError,
              },
              event,
            );
          },

          onComplete: () => {
            setIsStreaming(false);
            setAbortController(null);
            thinking.finalizeToolCalls(toolCalls.length > 0 ? [...toolCalls] : []);
            const subKaniActivity = snapshotSubKaniActivityFromBuffers(
              subKaniCallsBuffer,
              subKaniStatusBuffer,
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
            // Use unconditional write (not ??) so downstream refetches can
            // never overwrite with undefined before React commits.
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

            if (effectiveStrategyId && !session.snapshotApplied) {
              getStrategy(effectiveStrategyId)
                .then((full) => {
                  setStrategy(full);
                  setStrategyMeta({
                    name: full.name,
                    recordType: full.recordType ?? undefined,
                    siteId: full.siteId,
                  });
                })
                .catch(() => {});
            }
            onStreamComplete?.();
          },

          onError: (error) => {
            console.error("Chat error:", error);
            setIsStreaming(false);
            setAbortController(null);
            thinking.finalizeToolCalls(toolCalls.length > 0 ? [...toolCalls] : []);
            setApiError(error.message || "Unable to reach the API.");
            onStreamError?.(error);
          },
        },
        streamContext,
        streamMode,
        controller.signal,
        modelSelection ?? undefined,
      );
    },
    [
      setMessages,
      thinking,
      sessionRef,
      createSession,
      siteId,
      strategyId,
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
      setUndoSnapshots,
      parseToolArguments,
      parseToolResult,
      applyGraphSnapshot,
      getStrategy,
      attachThinkingToLastAssistant,
      modelSelection,
      onPlanSessionId,
      onPlanningArtifactUpdate,
      onExecutorBuildRequest,
      onConversationTitleUpdate,
      onApiError,
      onStreamComplete,
      onStreamError,
    ],
  );

  /** User-initiated send — appends a visible user message then streams. */
  const handleSendMessage = useCallback(
    async (content: string) => {
      const finalContent = encodeNodeSelection(draftSelection, content);
      const userMessage: Message = {
        role: "user",
        content: finalContent,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);
      if (draftSelection) {
        setDraftSelection(null);
      }

      const streamContext =
        mode === "plan"
          ? {
              planSessionId: planSessionId ?? undefined,
              referenceStrategyId: referenceStrategyId ?? undefined,
            }
          : {
              strategyId: strategyId ?? undefined,
              referenceStrategyId: referenceStrategyId ?? undefined,
            };

      await executeStream(finalContent, mode, streamContext);
    },
    [
      draftSelection,
      planSessionId,
      setMessages,
      setDraftSelection,
      strategyId,
      mode,
      referenceStrategyId,
      executeStream,
    ],
  );

  /**
   * System-initiated execution — sends the prompt to the model without
   * adding a visible user message.  Used for the plan→execute auto-handoff.
   */
  const handleAutoExecute = useCallback(
    async (prompt: string, targetStrategyId: string) => {
      await executeStream(prompt, "execute", { strategyId: targetStrategyId });
    },
    [executeStream],
  );

  return {
    handleSendMessage,
    handleAutoExecute,
    stopStreaming,
    isStreaming,
    apiError,
    setIsStreaming,
    optimizationProgress,
  };
}
