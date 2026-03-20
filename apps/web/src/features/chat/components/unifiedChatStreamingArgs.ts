import type { Dispatch, SetStateAction } from "react";
import type { Message, ModelSelection, ToolCall, Strategy } from "@pathfinder/shared";
import type { NodeSelection } from "@/lib/types/nodeSelection";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import type { GraphSnapshotInput } from "@/features/chat/utils/graphSnapshot";
import type { ToolResultPayload } from "@/features/chat/utils/parseToolResult";
import type { ToolArguments } from "@/features/chat/utils/parseToolArguments";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";

type ThinkingState = ReturnType<typeof useThinkingState>;

interface BuildUnifiedChatStreamingArgsParams {
  siteId: string;
  strategyId: string | null;
  draftSelection: NodeSelection | null;
  setDraftSelection: Dispatch<SetStateAction<NodeSelection | null>>;
  thinking: ThinkingState;
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setUndoSnapshots: Dispatch<SetStateAction<Record<number, Strategy>>>;
  sessionRef: { current: StreamingSession | null };
  createSession: () => StreamingSession;
  loadGraph: (graphId: string) => void;
  addStrategy: (s: Strategy) => void;
  addExecutedStrategy: (s: Strategy) => void;
  setStrategyIdGlobal: (id: string | null) => void;
  setWdkInfo: (
    wdkStrategyId: number,
    wdkUrl?: string | null,
    name?: string | null,
    description?: string | null,
  ) => void;
  setStrategy: (strategy: Strategy | null) => void;
  setStrategyMeta: (meta: Partial<Strategy>) => void;
  clearStrategy: () => void;
  addStep: (step: Strategy["steps"][number]) => void;
  parseToolArguments: (args: unknown) => ToolArguments;
  parseToolResult: (result?: string | null) => ToolResultPayload | null;
  applyGraphSnapshot: (graphSnapshot: GraphSnapshotInput) => void;
  getStrategy: (id: string) => Promise<Strategy>;
  currentStrategy: Strategy | null;
  attachThinkingToLastAssistant: (
    calls: ToolCall[],
    activity?: {
      calls: Record<string, ToolCall[]>;
      status: Record<string, string>;
    },
  ) => void;
  currentModelSelection: ModelSelection | undefined;
  setSelectedModelId?: (modelId: string | null) => void;
  setChatIsStreaming: (value: boolean) => void;
  handleError: (error: unknown, fallback: string) => void;
  onWorkbenchGeneSet?: (geneSet: {
    id: string;
    name: string;
    geneCount: number;
    source: string;
    siteId: string;
  }) => void;
}

export function useUnifiedChatStreamingArgs({
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
  setSelectedModelId,
  setChatIsStreaming,
  handleError,
  onWorkbenchGeneSet,
}: BuildUnifiedChatStreamingArgsParams) {
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
    ...(setSelectedModelId != null ? { setSelectedModelId } : {}),
    ...(currentModelSelection != null ? { modelSelection: currentModelSelection } : {}),
    ...(onWorkbenchGeneSet != null ? { onWorkbenchGeneSet } : {}),
    onStreamComplete: () => setChatIsStreaming(false),
    onStreamError: (error: Error) => {
      setChatIsStreaming(false);
      handleError(error, "Unable to reach the API.");
    },
  };
}
