import { useCallback } from "react";
import type {
  ChatMention,
  Message,
  ToolCall,
  ModelSelection,
  Step,
  Strategy,
} from "@pathfinder/shared";
import type { NodeSelection } from "@/lib/types/nodeSelection";
import { streamChat } from "@/features/chat/stream";
import { useSettingsStore } from "@/state/useSettingsStore";
import { encodeNodeSelection } from "@/features/chat/node_selection";
import type { GraphSnapshotInput } from "@/features/chat/utils/graphSnapshot";
import type { ChatEventContext } from "@/features/chat/handlers/handleChatEvent";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import { useStreamLifecycle } from "@/features/chat/hooks/useStreamLifecycle";
import { useStreamEvents } from "@/features/chat/hooks/useStreamEvents";

type Thinking = ReturnType<typeof useThinkingState>;
type AddStrategyInput = Parameters<ChatEventContext["addStrategy"]>[0];

interface UseChatStreamingArgs {
  siteId: string;
  strategyId: string | null;
  draftSelection: NodeSelection | null;
  setDraftSelection: (selection: NodeSelection | null) => void;
  thinking: Thinking;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  setUndoSnapshots: React.Dispatch<React.SetStateAction<Record<number, Strategy>>>;
  sessionRef: { current: StreamingSession | null };
  createSession: () => StreamingSession;
  loadGraph: (graphId: string) => void;
  addStrategy: (strategy: AddStrategyInput) => void;
  addExecutedStrategy: (strategy: Strategy) => void;
  setStrategyId: (id: string | null) => void;
  setWdkInfo: ChatEventContext["setWdkInfo"];
  setStrategy: (strategy: Strategy | null) => void;
  setStrategyMeta: ChatEventContext["setStrategyMeta"];
  clearStrategy: () => void;
  addStep: (step: Step) => void;
  parseToolArguments: ChatEventContext["parseToolArguments"];
  parseToolResult: ChatEventContext["parseToolResult"];
  applyGraphSnapshot: (graphSnapshot: GraphSnapshotInput) => void;
  getStrategy: (id: string) => Promise<Strategy>;
  currentStrategy: Strategy | null;
  attachThinkingToLastAssistant: (
    calls: ToolCall[],
    activity?: { calls: Record<string, ToolCall[]>; status: Record<string, string> },
  ) => void;
  /** Called when the backend selects a model (model_selected event). */
  setSelectedModelId?: (modelId: string | null) => void;
  /** Per-request model/provider/reasoning selection. */
  modelSelection?: ModelSelection | null;
  onApiError?: (message: string) => void;
  /** Callback for workbench_gene_set events — decouples from workbench store. */
  onWorkbenchGeneSet?: ChatEventContext["onWorkbenchGeneSet"];
  /** Called after streaming completes successfully. */
  onStreamComplete?: () => void;
  /** Called after streaming errors out (in addition to the default error handling). */
  onStreamError?: (error: Error) => void;
  /** Called whenever streaming state changes (e.g. to sync global store). */
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
      streamContext: { strategyId?: string; mentions?: ChatMention[] },
    ) => {
      lifecycle.beginStream();

      const session = createSession();
      sessionRef.current = session;

      const effectiveStrategyId = streamContext.strategyId ?? strategyId;

      const callbacks = buildStreamCallbacks(
        session,
        effectiveStrategyId ?? null,
        (toolCalls: ToolCall[]) => {
          lifecycle.finalizeStream(toolCalls);
          onStreamComplete?.();
        },
        (error: Error, toolCalls: ToolCall[]) => {
          lifecycle.handleStreamError(error, toolCalls, onStreamError);
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
      } catch (e) {
        const error = e instanceof Error ? e : new Error(String(e));
        lifecycle.handleStreamError(error, callbacks.toolCalls, onStreamError);
      }
    },
    [
      lifecycle,
      createSession,
      sessionRef,
      strategyId,
      buildStreamCallbacks,
      siteId,
      modelSelection,
      setStrategyId,
      onStreamComplete,
      onStreamError,
    ],
  );

  // --- Public API ---
  const handleSendMessage = useCallback(
    async (content: string, mentions?: ChatMention[]) => {
      const finalContent = encodeNodeSelection(draftSelection, content);
      const userMessage: Message = {
        role: "user",
        content: finalContent,
        ...(mentions != null && mentions.length > 0 ? { mentions } : {}),
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);
      if (draftSelection) {
        setDraftSelection(null);
      }

      await executeStream(finalContent, {
        ...(strategyId != null ? { strategyId } : {}),
        ...(mentions != null ? { mentions } : {}),
      });
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
