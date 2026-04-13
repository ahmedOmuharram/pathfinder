import type { Dispatch, SetStateAction } from "react";
import type {
  Message,
  PipelineConfig,
  ToolCall,
  Citation,
  PlanningArtifact,
  OptimizationProgressData,
  ProblemFrame,
  Step,
  Strategy,
} from "@pathfinder/shared";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import type { GraphSnapshotInput } from "@/features/chat/utils/graphSnapshot";
import type { ToolResultPayload } from "@/features/chat/utils/parseToolResult";
import type { ToolArguments } from "@/features/chat/utils/parseToolArguments";

type Thinking = ReturnType<typeof useThinkingState>;

// ── Stream session state ────────────────────────────────────────────

export type StreamSessionState = {
  streamingAssistantIndex: number | null;
  streamingAssistantMessageId: string | null;
  assistantMessageIndices: Record<string, number>;
  turnAssistantIndex?: number | null;
  lastAssistantMessageId?: string | null;
  messageGroupId?: string | null;
  currentPhase?: string | null;
  pipeline?: PipelineConfig | null;
  reasoning: string | null;
  optimizationProgress: OptimizationProgressData | null;
  currentModelId: string | null;
};

// ── Sub-interfaces (ISP) ────────────────────────────────────────────

/** Mutable per-stream buffers — allocated fresh for each stream. */
export interface StreamBuffers {
  toolCallsBuffer: ToolCall[];
  citationsBuffer: Citation[];
  planningArtifactsBuffer: PlanningArtifact[];
  problemFrameBuffer: ProblemFrame | null;
}

/** Strategy store mutations — used by strategy events and message_start. */
export interface StrategyActions {
  setStrategyId: (id: string | null) => void;
  addStrategy: (s: Strategy) => void;
  addExecutedStrategy: (s: Strategy) => void;
  setWdkInfo: (
    wdkStrategyId: number,
    wdkUrl?: string | null,
    name?: string | null,
    description?: string | null,
  ) => void;
  setStrategy: (s: Strategy | null) => void;
  setStrategyMeta: (u: Partial<Strategy>) => void;
  clearStrategy: () => void;
  addStep: (s: Step) => void;
  loadGraph: (graphId: string) => void;
}

/** React state setters for UI updates. */
export interface UISetters {
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setUndoSnapshots: Dispatch<SetStateAction<Record<number, Strategy>>>;
  setOptimizationProgress: Dispatch<SetStateAction<OptimizationProgressData | null>>;
}

/** Parsing and snapshot helpers. */
export interface EventHelpers {
  parseToolArguments: (args: unknown) => ToolArguments;
  parseToolResult: (result?: string | null) => ToolResultPayload | null;
  applyGraphSnapshot: (graphSnapshot: GraphSnapshotInput) => void;
  getStrategy: (id: string) => Promise<Strategy>;
}

/** Per-stream identity and session state. */
export interface StreamContext {
  siteId: string;
  strategyIdAtStart: string | null;
  session: StreamingSession;
  currentStrategy: Strategy | null;
  streamState: StreamSessionState;
  thinking: Thinking;
}

/** Optional callbacks injected from the page layer. */
export interface OptionalCallbacks {
  setSelectedModelId?: (modelId: string | null) => void;
  onApiError?: (message: string) => void;
  onWorkbenchGeneSet?: (geneSet: {
    id: string;
    name: string;
    geneCount: number;
    source: string;
    siteId: string;
  }) => void;
}

// ── Full context (composition of sub-interfaces) ────────────────────

export type ChatEventContext =
  & StreamBuffers
  & StrategyActions
  & UISetters
  & EventHelpers
  & StreamContext
  & OptionalCallbacks;
