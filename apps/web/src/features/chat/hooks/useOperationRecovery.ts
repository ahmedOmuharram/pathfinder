/**
 * Recover active chat operations on page load / strategy change.
 *
 * When the user refreshes while a chat operation is in-flight, this hook
 * discovers the active operation and re-subscribes to its SSE stream so
 * the UI resumes where it left off.
 */

import { useQuery } from "@tanstack/react-query";
import { useEventCallback } from "usehooks-ts";
import type {
  Citation,
  Message,
  PipelineConfig,
  PlanningArtifact,
  ProblemFrame,
  Strategy,
  ToolCall,
} from "@pathfinder/shared";
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

// Pipeline phase names in the fixed 5-phase order the backend guarantees.
const PIPELINE_PHASES = [
  "scoping",
  "discovery",
  "planning",
  "execution",
  "verification",
] as const;

const PIPELINE_PHASE_SET: ReadonlySet<string> = new Set(PIPELINE_PHASES);

function isPipelinePhaseName(v: string): boolean {
  return PIPELINE_PHASE_SET.has(v);
}

function asRecord(v: unknown): Record<string, unknown> | null {
  if (v == null || typeof v !== "object" || Array.isArray(v)) return null;
  return v as Record<string, unknown>;
}

/**
 * Narrow a ``JSONObject | null`` pipeline payload to ``PipelineConfig``.
 *
 * Returns ``null`` when any phase entry is missing, is not an object, or
 * lacks the required ``modelId`` / ``reasoningEffort`` string fields. This
 * is the single chokepoint where unstructured REST data is validated into
 * the strongly typed pipeline shape that ``streamState`` consumes.
 */
function narrowPipeline(raw: unknown): PipelineConfig | null {
  const root = asRecord(raw);
  if (root == null) return null;
  for (const phase of PIPELINE_PHASES) {
    const entry = asRecord(root[phase]);
    if (entry == null) return null;
    if (
      typeof entry["modelId"] !== "string"
      || typeof entry["reasoningEffort"] !== "string"
    ) {
      return null;
    }
  }
  return root as unknown as PipelineConfig;
}

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
    (sid: string, event: ReturnType<typeof parseChatSSEEvent>, session: StreamingSession, streamState: ChatEventContext["streamState"], toolCalls: ToolCall[], citationsBuffer: Citation[], planningArtifactsBuffer: PlanningArtifact[], problemFrameRef: { current: ProblemFrame | null }) => {
      if (event == null) return;
      handleChatEvent(
        {
          siteId,
          strategyIdAtStart: sid,
          toolCallsBuffer: toolCalls,
          citationsBuffer,
          planningArtifactsBuffer,
          get problemFrameBuffer() {
            return problemFrameRef.current;
          },
          set problemFrameBuffer(value) {
            problemFrameRef.current = value;
          },
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

      // Seed streamState from the REST-loaded strategy so that messages
      // streamed during recovery are tagged with the correct phase / model
      // even when the recovery cursor starts AFTER the original
      // model_selected / phase_change events were emitted.
      const seedPipeline = narrowPipeline(currentStrategy?.pipeline ?? null);
      const csRecord = asRecord(currentStrategy?.conversationState ?? null);
      const rawSeedPhase = csRecord?.["currentPhase"];
      const seedPhase =
        typeof rawSeedPhase === "string" && isPipelinePhaseName(rawSeedPhase)
          ? rawSeedPhase
          : null;
      const seedModelId = seedPipeline != null ? seedPipeline.planning.modelId : null;

      // Re-seed the UI modelId so the model icon/name appears even when
      // the SSE recovery subscription never re-emits ``model_selected``.
      if (seedModelId != null && setSelectedModelId != null) {
        setSelectedModelId(seedModelId);
      }

      const session = new StreamingSession();
      const streamState: ChatEventContext["streamState"] = {
        streamingAssistantIndex: null,
        streamingAssistantMessageId: null,
        assistantMessageIndices: {},
        turnAssistantIndex: null,
        lastAssistantMessageId: null,
        messageGroupId: null,
        currentPhase: seedPhase,
        pipeline: seedPipeline,
        reasoning: null,
        optimizationProgress: null,
        currentModelId: seedModelId,
      };
      const toolCalls: ToolCall[] = [];
      const citationsBuffer: Citation[] = [];
      const planningArtifactsBuffer: PlanningArtifact[] = [];
      const problemFrameRef: { current: ProblemFrame | null } = { current: null };

      return new Promise<null>((resolve, reject) => {
        const sub = subscribeToOperation<RawSSEData>(opId, {
          onEvent: ({ type, data }) => {
            const event = parseChatSSEEvent({ type, data });
            handleEvent(
              sid,
              event,
              session,
              streamState,
              toolCalls,
              citationsBuffer,
              planningArtifactsBuffer,
              problemFrameRef,
            );
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
    enabled:
      activeOp != null &&
      strategyId != null &&
      strategyId !== "" &&
      !isStreaming,
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
  });
}
