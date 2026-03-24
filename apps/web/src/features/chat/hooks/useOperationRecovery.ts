/**
 * Recover active chat operations on page load / strategy change.
 *
 * When the user refreshes while a chat operation is in-flight, this hook
 * discovers the active operation and re-subscribes to its SSE stream so
 * the UI resumes where it left off.
 */

import { useEffect, useRef } from "react";
import type { Message, ToolCall, Strategy } from "@pathfinder/shared";
import type { Dispatch, SetStateAction } from "react";
import {
  fetchActiveOperations,
  subscribeToOperation,
  type OperationSubscription,
} from "@/lib/operationSubscribe";
import { parseChatSSEEvent, type RawSSEData } from "@/lib/sse_events";
import { handleChatEvent } from "@/features/chat/handlers/handleChatEvent";
import type { ChatEventContext } from "@/features/chat/handlers/handleChatEvent";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import { snapshotSubKaniActivityFromBuffers } from "@/features/chat/handlers/handleChatEvent.messageEvents";

interface UseOperationRecoveryArgs {
  strategyId: string | null;
  siteId: string;
  isStreaming: boolean;
  setIsStreaming: (v: boolean) => void;
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setUndoSnapshots: Dispatch<SetStateAction<Record<number, Strategy>>>;
  thinking: ReturnType<typeof useThinkingState>;
  currentStrategy: Strategy | null;
  setStrategyId: (id: string | null) => void;
  addStrategy: ChatEventContext["addStrategy"];
  addExecutedStrategy: (s: Strategy) => void;
  setWdkInfo: ChatEventContext["setWdkInfo"];
  setStrategy: (s: Strategy | null) => void;
  setStrategyMeta: ChatEventContext["setStrategyMeta"];
  clearStrategy: () => void;
  addStep: ChatEventContext["addStep"];
  loadGraph: (id: string) => void;
  parseToolArguments: ChatEventContext["parseToolArguments"];
  parseToolResult: ChatEventContext["parseToolResult"];
  applyGraphSnapshot: ChatEventContext["applyGraphSnapshot"];
  getStrategy: (id: string) => Promise<Strategy>;
  attachThinkingToLastAssistant: (
    calls: ToolCall[],
    activity?: { calls: Record<string, ToolCall[]>; status: Record<string, string> },
  ) => void;
  setSelectedModelId?: ((modelId: string | null) => void) | undefined;
  onApiError?: ((msg: string) => void) | undefined;
  setOptimizationProgress: ChatEventContext["setOptimizationProgress"];
  onWorkbenchGeneSet?: ChatEventContext["onWorkbenchGeneSet"] | undefined;
}

/**
 * On mount (or when strategyId changes), check for active chat operations
 * and re-subscribe to resume streaming.
 */
export function useOperationRecovery({
  strategyId,
  siteId,
  isStreaming,
  setIsStreaming,
  setMessages,
  setUndoSnapshots,
  thinking,
  currentStrategy,
  setStrategyId,
  addStrategy,
  addExecutedStrategy,
  setWdkInfo,
  setStrategy,
  setStrategyMeta,
  clearStrategy,
  addStep,
  loadGraph,
  parseToolArguments,
  parseToolResult,
  applyGraphSnapshot,
  getStrategy,
  attachThinkingToLastAssistant,
  setSelectedModelId,
  onApiError,
  setOptimizationProgress,
  onWorkbenchGeneSet,
}: UseOperationRecoveryArgs) {
  const recoveredRef = useRef<string | null>(null);
  const subscriptionRef = useRef<OperationSubscription | null>(null);

  // Capture all callback/value dependencies in a ref so the effect closure
  // always sees the latest values without needing them in the dep array.
  // This preserves the original behavior: the effect fires only on
  // strategyId changes.
  const callbacksRef = useRef<UseOperationRecoveryArgs>({
    strategyId,
    siteId,
    isStreaming,
    setIsStreaming,
    setMessages,
    setUndoSnapshots,
    thinking,
    currentStrategy,
    setStrategyId,
    addStrategy,
    addExecutedStrategy,
    setWdkInfo,
    setStrategy,
    setStrategyMeta,
    clearStrategy,
    addStep,
    loadGraph,
    parseToolArguments,
    parseToolResult,
    applyGraphSnapshot,
    getStrategy,
    attachThinkingToLastAssistant,
    setSelectedModelId,
    onApiError,
    setOptimizationProgress,
    onWorkbenchGeneSet,
  });
  callbacksRef.current = {
    strategyId,
    siteId,
    isStreaming,
    setIsStreaming,
    setMessages,
    setUndoSnapshots,
    thinking,
    currentStrategy,
    setStrategyId,
    addStrategy,
    addExecutedStrategy,
    setWdkInfo,
    setStrategy,
    setStrategyMeta,
    clearStrategy,
    addStep,
    loadGraph,
    parseToolArguments,
    parseToolResult,
    applyGraphSnapshot,
    getStrategy,
    attachThinkingToLastAssistant,
    setSelectedModelId,
    onApiError,
    setOptimizationProgress,
    onWorkbenchGeneSet,
  };

  useEffect(() => {
    if (!strategyId) return;
    // Read isStreaming from the ref to avoid adding it as a dep.
    if (callbacksRef.current.isStreaming) return;
    // Only recover once per strategyId to avoid re-subscribing loops.
    if (recoveredRef.current === strategyId) return;
    recoveredRef.current = strategyId;

    let cancelled = false;

    fetchActiveOperations({ type: "chat", streamId: strategyId })
      .then((ops) => {
        const op = ops[0];
        if (cancelled || op == null) return;
        // Pick the most recent active operation.

        const cb = callbacksRef.current;

        cb.setIsStreaming(true);
        cb.thinking.reset();

        const session = new StreamingSession(cb.currentStrategy);
        const streamState: ChatEventContext["streamState"] = {
          streamingAssistantIndex: null,
          streamingAssistantMessageId: null,
          turnAssistantIndex: null,
          reasoning: null,
          optimizationProgress: null,
        };
        const toolCalls: ToolCall[] = [];
        const citationsBuffer: import("@pathfinder/shared").Citation[] = [];
        const planningArtifactsBuffer: import("@pathfinder/shared").PlanningArtifact[] =
          [];
        const subKaniCallsBuffer: Record<string, ToolCall[]> = {};
        const subKaniStatusBuffer: Record<string, string> = {};
        const subKaniModelsBuffer: Record<string, string> = {};
        const subKaniTokenUsageBuffer: Record<
          string,
          import("@pathfinder/shared").SubKaniTokenUsage
        > = {};

        const sub = subscribeToOperation<RawSSEData>(op.operationId, {
          onEvent: ({ type, data }) => {
            const event = parseChatSSEEvent({ type, data });
            if (!event) return;
            const latest = callbacksRef.current;
            handleChatEvent(
              {
                siteId: latest.siteId,
                strategyIdAtStart: strategyId,
                toolCallsBuffer: toolCalls,
                citationsBuffer,
                planningArtifactsBuffer,
                subKaniCallsBuffer,
                subKaniStatusBuffer,
                subKaniModelsBuffer,
                subKaniTokenUsageBuffer,
                thinking: latest.thinking,
                setStrategyId: latest.setStrategyId,
                addStrategy: latest.addStrategy,
                addExecutedStrategy: latest.addExecutedStrategy,
                setWdkInfo: latest.setWdkInfo,
                setStrategy: latest.setStrategy,
                setStrategyMeta: latest.setStrategyMeta,
                clearStrategy: latest.clearStrategy,
                addStep: latest.addStep,
                loadGraph: latest.loadGraph,
                session,
                currentStrategy: latest.currentStrategy,
                setMessages: latest.setMessages,
                setUndoSnapshots: latest.setUndoSnapshots,
                parseToolArguments: latest.parseToolArguments,
                parseToolResult: latest.parseToolResult,
                applyGraphSnapshot: latest.applyGraphSnapshot,
                getStrategy: latest.getStrategy,
                streamState,
                setOptimizationProgress: latest.setOptimizationProgress,
                ...(latest.setSelectedModelId != null
                  ? { setSelectedModelId: latest.setSelectedModelId }
                  : {}),
                ...(latest.onApiError != null
                  ? { onApiError: latest.onApiError }
                  : {}),
                ...(latest.onWorkbenchGeneSet != null
                  ? { onWorkbenchGeneSet: latest.onWorkbenchGeneSet }
                  : {}),
              },
              event,
            );
          },
          onComplete: () => {
            const latest = callbacksRef.current;
            latest.setIsStreaming(false);
            subscriptionRef.current = null;
            latest.thinking.finalizeToolCalls(
              toolCalls.length > 0 ? [...toolCalls] : [],
            );
            const activity = snapshotSubKaniActivityFromBuffers(
              subKaniCallsBuffer,
              subKaniStatusBuffer,
              subKaniModelsBuffer,
              subKaniTokenUsageBuffer,
            );
            latest.attachThinkingToLastAssistant(
              toolCalls.length > 0 ? [...toolCalls] : [],
              activity,
            );
          },
          onError: () => {
            callbacksRef.current.setIsStreaming(false);
            subscriptionRef.current = null;
          },
          endEventTypes: new Set(["message_end"]),
        });

        subscriptionRef.current = sub;
      })
      .catch(() => {
        // Discovery failed — not critical, user can still interact.
      });

    return () => {
      cancelled = true;
      subscriptionRef.current?.unsubscribe();
      subscriptionRef.current = null;
      // Reset so returning to this strategy (A→B→A) triggers recovery again.
      recoveredRef.current = null;
    };
  }, [strategyId]);
}
