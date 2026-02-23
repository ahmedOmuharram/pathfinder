import type { Dispatch, SetStateAction } from "react";
import type { ChatMode, Message, PlanningArtifact, ToolCall } from "@pathfinder/shared";
import type { StrategyWithMeta } from "@/features/strategy/types";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import type { GraphSnapshotInput } from "@/features/chat/utils/graphSnapshot";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";

type ThinkingState = ReturnType<typeof useThinkingState>;

type Noop = () => void;
const noop: Noop = () => {};
const noopPromise = () => Promise.resolve(null as never);

const noopSetUndoSnapshots: Dispatch<
  SetStateAction<Record<number, StrategyWithMeta>>
> = () => {};

interface BuildUnifiedChatStreamingArgsParams {
  chatMode: ChatMode;
  siteId: string;
  strategyId: string | null;
  planSessionId: string | null;
  draftSelection: Record<string, unknown> | null;
  setDraftSelection: Dispatch<SetStateAction<Record<string, unknown> | null>>;
  thinking: ThinkingState;
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setUndoSnapshots: Dispatch<SetStateAction<Record<number, StrategyWithMeta>>>;
  sessionRef: { current: StreamingSession | null };
  createSession: () => StreamingSession;
  loadGraph: (graphId: string) => void;
  addStrategy: (s: {
    id: string;
    name: string;
    title: string;
    siteId: string;
    recordType: string | null;
    stepCount: number;
    resultCount?: number;
    wdkStrategyId?: number;
    createdAt: string;
    updatedAt: string;
  }) => void;
  addExecutedStrategy: (s: StrategyWithMeta) => void;
  setStrategyIdGlobal: (id: string | null) => void;
  setWdkInfo: (
    wdkStrategyId: number,
    wdkUrl?: string | null,
    name?: string | null,
    description?: string | null,
  ) => void;
  setStrategy: (strategy: StrategyWithMeta | null) => void;
  setStrategyMeta: (meta: Partial<StrategyWithMeta>) => void;
  clearStrategy: () => void;
  addStep: (step: StrategyWithMeta["steps"][number]) => void;
  parseToolArguments: (args: unknown) => Record<string, unknown>;
  parseToolResult: (
    result?: string | null,
  ) => { graphSnapshot?: Record<string, unknown> } | null;
  applyGraphSnapshot: (graphSnapshot: GraphSnapshotInput) => void;
  getStrategy: (id: string) => Promise<StrategyWithMeta>;
  currentStrategy: StrategyWithMeta | null;
  attachThinkingToLastAssistant: (
    calls: ToolCall[],
    activity?: {
      calls: Record<string, ToolCall[]>;
      status: Record<string, string>;
    },
  ) => void;
  currentModelSelection: ReturnType<
    typeof import("@/features/chat/components/MessageComposer").buildModelSelection
  >;
  referenceStrategyIdProp?: string | null;
  onPlanSessionId: (id: string) => void;
  onPlanningArtifactUpdate: (artifact: PlanningArtifact) => void;
  onExecutorBuildRequest: (message: string) => void;
  onConversationTitleUpdate: (title: string) => void;
  setApiError: Dispatch<SetStateAction<string | null>>;
  onStreamComplete: () => void;
  onStreamError: (error: Error) => void;
  setChatIsStreaming: (value: boolean) => void;
  handleError: (error: unknown, fallback: string) => void;
}

export function useUnifiedChatStreamingArgs({
  chatMode,
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
  setStrategyIdGlobal,
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
  currentModelSelection,
  referenceStrategyIdProp,
  onPlanSessionId,
  onPlanningArtifactUpdate,
  onExecutorBuildRequest,
  onConversationTitleUpdate,
  setApiError,
  onStreamComplete,
  onStreamError,
  setChatIsStreaming,
  handleError,
}: BuildUnifiedChatStreamingArgsParams) {
  if (chatMode === "plan") {
    return {
      siteId,
      strategyId: null as string | null,
      planSessionId,
      draftSelection: null,
      setDraftSelection: noop as Dispatch<
        SetStateAction<Record<string, unknown> | null>
      >,
      thinking,
      setMessages,
      setUndoSnapshots: noopSetUndoSnapshots,
      sessionRef,
      createSession,
      loadGraph: noop,
      addStrategy: noop,
      addExecutedStrategy: noop,
      setStrategyId: noop as (id: string | null) => void,
      setWdkInfo: noop,
      setStrategy: noop as (s: StrategyWithMeta | null) => void,
      setStrategyMeta: noop as (m: Record<string, unknown>) => void,
      clearStrategy: noop,
      addStep: noop,
      parseToolArguments,
      parseToolResult: () => null,
      applyGraphSnapshot: noop,
      getStrategy: noopPromise,
      currentStrategy: null,
      attachThinkingToLastAssistant: noop,
      mode: "plan" as ChatMode,
      modelSelection: currentModelSelection,
      referenceStrategyId: referenceStrategyIdProp,
      onPlanSessionId,
      onPlanningArtifactUpdate,
      onExecutorBuildRequest,
      onConversationTitleUpdate,
      onApiError: (msg: string) => setApiError(msg),
      onStreamComplete,
      onStreamError,
    };
  }

  return {
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
    setStrategyId: setStrategyIdGlobal,
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
    mode: "execute" as ChatMode,
    modelSelection: currentModelSelection,
    referenceStrategyId: referenceStrategyIdProp,
    onStreamComplete: () => setChatIsStreaming(false),
    onStreamError: (error: Error) => {
      setChatIsStreaming(false);
      handleError(error, "Unable to reach the API.");
    },
  };
}
