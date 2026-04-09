/**
 * Recover active chat operations on page load / strategy change.
 *
 * When the user refreshes while a chat operation is in-flight, this hook
 * discovers the active operation and re-subscribes to its SSE stream so
 * the UI resumes where it left off.
 */

import { useQuery } from "@tanstack/react-query";
import { useEventCallback } from "usehooks-ts";
import type { Message, ToolCall, Strategy, Citation, PlanningArtifact } from "@pathfinder/shared";
import type { Dispatch, SetStateAction } from "react";
import { useSessionStore } from "@/state/useSessionStore";
import {
  fetchActiveOperations,
  subscribeToOperation,
} from "@/lib/operationSubscribe";
import { parseChatSSEEvent, type RawSSEData } from "@/lib/sse_events";
import { handleChatEvent } from "@/features/chat/handlers/handleChatEvent";
import type { ChatEventContext } from "@/features/chat/handlers/handleChatEvent";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import { StreamingSession } from "@/features/chat/streaming/StreamingSession";

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
  attachThinkingToLastAssistant: (calls: ToolCall[]) => void;
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
  const authRefreshed = useSessionStore((s) => s.authRefreshed);

  const handleEvent = useEventCallback(
    (sid: string, event: ReturnType<typeof parseChatSSEEvent>, session: StreamingSession, streamState: ChatEventContext["streamState"], toolCalls: ToolCall[], citationsBuffer: Citation[], planningArtifactsBuffer: PlanningArtifact[]) => {
      if (event == null) return;
      handleChatEvent(
        {
          siteId,
          strategyIdAtStart: sid,
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
        },
        event,
      );
    },
  );

  const handleComplete = useEventCallback((toolCalls: ToolCall[]) => {
    setIsStreaming(false);
    thinking.finalizeToolCalls(toolCalls.length > 0 ? [...toolCalls] : []);
    attachThinkingToLastAssistant(toolCalls.length > 0 ? [...toolCalls] : []);
  });

  const handleError = useEventCallback(() => {
    setIsStreaming(false);
  });

  const { data: activeOp } = useQuery({
    queryKey: ["operation-recovery", strategyId] as const,
    queryFn: async () => {
      const ops = await fetchActiveOperations({ type: "chat", streamId: strategyId! });
      return ops[0] ?? null;
    },
    enabled: strategyId != null && strategyId !== "" && !isStreaming && authRefreshed,
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
  });

  useQuery({
    queryKey: ["operation-recovery-stream", activeOp?.operationId] as const,
    queryFn: ({ signal }) => {
      const sid = strategyId!;
      const opId = activeOp!.operationId;

      setIsStreaming(true);
      thinking.reset();

      const session = new StreamingSession();
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

      return new Promise<null>((resolve, reject) => {
        const sub = subscribeToOperation<RawSSEData>(opId, {
          onEvent: ({ type, data }) => {
            const event = parseChatSSEEvent({ type, data });
            handleEvent(sid, event, session, streamState, toolCalls, citationsBuffer, planningArtifactsBuffer);
          },
          onComplete: () => {
            handleComplete(toolCalls);
            resolve(null);
          },
          onError: () => {
            handleError();
            reject(new Error("SSE stream error during recovery"));
          },
          endEventTypes: new Set(["message_end"]),
        });

        signal.addEventListener("abort", () => sub.unsubscribe());
      });
    },
    enabled: activeOp != null && strategyId != null && strategyId !== "",
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
  });
}
