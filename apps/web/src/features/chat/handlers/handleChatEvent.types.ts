import type { Dispatch, SetStateAction } from "react";
import type {
  Message,
  ToolCall,
  Citation,
  PlanningArtifact,
  OptimizationProgressData,
} from "@pathfinder/shared";
import type { StrategyStep, StrategyWithMeta } from "@/features/strategy/types";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";

type Thinking = ReturnType<typeof useThinkingState>;

export type StreamSessionState = {
  streamingAssistantIndex: number | null;
  streamingAssistantMessageId: string | null;
  /** Owner assistant message for the current stream turn. */
  turnAssistantIndex?: number | null;
  reasoning: string | null;
  optimizationProgress: OptimizationProgressData | null;
};

export type ChatEventContext = {
  siteId: string;
  strategyIdAtStart: string | null;
  toolCallsBuffer: ToolCall[];
  citationsBuffer: Citation[];
  planningArtifactsBuffer: PlanningArtifact[];
  subKaniCallsBuffer: Record<string, ToolCall[]>;
  subKaniStatusBuffer: Record<string, string>;
  thinking: Thinking;

  // Strategy/session actions
  setStrategyId: (id: string | null) => void;
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
  setWdkInfo: (
    wdkStrategyId: number,
    wdkUrl?: string | null,
    name?: string | null,
    description?: string | null,
  ) => void;
  setStrategy: (s: StrategyWithMeta | null) => void;
  setStrategyMeta: (u: Partial<StrategyWithMeta>) => void;
  clearStrategy: () => void;
  addStep: (s: StrategyStep) => void;
  loadGraph: (graphId: string) => void;

  /** Mutable streaming session scoped to this stream. */
  session: StreamingSession;
  currentStrategy: StrategyWithMeta | null;

  // UI state setters
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setUndoSnapshots: Dispatch<SetStateAction<Record<number, StrategyWithMeta>>>;

  // Helpers
  parseToolArguments: (args: unknown) => Record<string, unknown>;
  parseToolResult: (
    result?: string | null,
  ) => { graphSnapshot?: Record<string, unknown> } | null;
  applyGraphSnapshot: (graphSnapshot: Record<string, unknown>) => void;
  getStrategy: (id: string) => Promise<StrategyWithMeta>;
  streamState: StreamSessionState;

  setOptimizationProgress: Dispatch<SetStateAction<OptimizationProgressData | null>>;

  onPlanSessionId?: (id: string) => void;
  onPlanningArtifactUpdate?: (artifact: PlanningArtifact) => void;
  onExecutorBuildRequest?: (message: string) => void;
  onConversationTitleUpdate?: (title: string) => void;
  onApiError?: (message: string) => void;
};
