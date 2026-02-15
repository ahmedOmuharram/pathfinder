import { useCallback, useRef, useState } from "react";
import type {
  Message,
  ToolCall,
  ChatMode,
  Citation,
  ModelSelection,
  PlanningArtifact,
} from "@pathfinder/shared";
import type { ChatSSEEvent } from "@/features/chat/sse_events";
import { streamChat } from "@/features/chat/stream";
import { handleChatEvent } from "@/features/chat/handlers/handleChatEvent";
import type { ChatEventContext } from "@/features/chat/handlers/handleChatEvent";
import { encodeNodeSelection } from "@/features/chat/node_selection";
import type { StrategyStep, StrategyWithMeta } from "@/types/strategy";
import type { GraphSnapshotInput } from "@/features/chat/utils/graphSnapshot";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import type { MutableRef } from "@/shared/types/refs";

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
  pendingUndoSnapshotRef: MutableRef<StrategyWithMeta | null>;
  appliedSnapshotRef: MutableRef<boolean>;
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
  strategyRef: MutableRef<StrategyWithMeta | null>;
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

  // --- Optional conversation callbacks ---
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
  pendingUndoSnapshotRef,
  appliedSnapshotRef,
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
  strategyRef,
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
  const abortRef = useRef<AbortController | null>(null);
  const streamingAssistantIndexRef = useRef<number | null>(null);
  const streamingAssistantMessageIdRef = useRef<string | null>(null);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

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
      setIsStreaming(true);
      setApiError(null);
      thinking.reset();
      pendingUndoSnapshotRef.current = null;
      appliedSnapshotRef.current = false;
      streamingAssistantIndexRef.current = null;
      streamingAssistantMessageIdRef.current = null;

      const toolCalls: ToolCall[] = [];
      const citationsBuffer: Citation[] = [];
      const planningArtifactsBuffer: PlanningArtifact[] = [];

      const controller = new AbortController();
      abortRef.current = controller;

      await streamChat(
        finalContent,
        siteId,
        {
          onMessage: (event: ChatSSEEvent) => {
            handleChatEvent(
              {
                siteId,
                strategyIdAtStart: strategyId,
                toolCallsBuffer: toolCalls,
                citationsBuffer,
                planningArtifactsBuffer,
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
                pendingUndoSnapshotRef,
                appliedSnapshotRef,
                strategyRef,
                currentStrategy,
                setMessages,
                setUndoSnapshots,
                parseToolArguments,
                parseToolResult,
                applyGraphSnapshot,
                getStrategy,
                streamingAssistantIndexRef,
                streamingAssistantMessageIdRef,
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
            abortRef.current = null;
            thinking.finalizeToolCalls(toolCalls.length > 0 ? [...toolCalls] : []);
            const subKaniActivity = thinking.snapshotSubKaniActivity();
            attachThinkingToLastAssistant(
              toolCalls.length > 0 ? [...toolCalls] : [],
              subKaniActivity,
            );
            if (strategyId && !appliedSnapshotRef.current) {
              getStrategy(strategyId)
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
            abortRef.current = null;
            thinking.finalizeToolCalls(toolCalls.length > 0 ? [...toolCalls] : []);
            setApiError(error.message || "Unable to reach the API.");
            onStreamError?.(error);
          },
        },
        mode === "plan"
          ? {
              planSessionId: planSessionId ?? undefined,
              referenceStrategyId: referenceStrategyId ?? undefined,
            }
          : { strategyId: strategyId ?? undefined },
        mode,
        controller.signal,
        modelSelection ?? undefined,
      );
    },
    [
      draftSelection,
      planSessionId,
      setMessages,
      setDraftSelection,
      thinking,
      pendingUndoSnapshotRef,
      appliedSnapshotRef,
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
      strategyRef,
      currentStrategy,
      setUndoSnapshots,
      parseToolArguments,
      parseToolResult,
      applyGraphSnapshot,
      getStrategy,
      attachThinkingToLastAssistant,
      mode,
      modelSelection,
      referenceStrategyId,
      onPlanSessionId,
      onPlanningArtifactUpdate,
      onExecutorBuildRequest,
      onConversationTitleUpdate,
      onApiError,
      onStreamComplete,
      onStreamError,
    ],
  );

  return { handleSendMessage, stopStreaming, isStreaming, apiError, setIsStreaming };
}
