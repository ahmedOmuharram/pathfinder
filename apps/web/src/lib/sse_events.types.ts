import type {
  Citation,
  PlanningArtifact,
  ProblemFrame,
  SSEErrorData,
  Strategy,
  StrategyPlan,
} from "@pathfinder/shared";
export type {
  UserMessageData,
  AssistantDeltaData,
  AssistantMessageData,
  ModelSelectedData,
  TokenUsagePartialData,
  StrategyMetaData,
  StrategyLinkData,
  GraphClearedData,
  ReasoningData,
  PlanningThoughtData,
  PlanPresentedData,
  PlanUpdatedData,
  DecisionPresentedData,
  PhaseChangeData,
  OptimizationProgressData,
} from "@pathfinder/shared";
import type { GraphSnapshotInput, StepParameters } from "@/lib/strategyGraph/types";

/**
 * Raw SSE event data before type-narrowing.
 * JSON-parsed payloads from the event stream are always string-keyed objects
 * with unknown values until narrowed by {@link parseChatSSEEvent}.
 */
export type RawSSEData = Record<string, unknown>;

/* ── Per-event data shapes ─────────────────────────────────────────── */
// Types that remain local — their local shapes differ from the generated
// equivalents (e.g., typed strategy vs JSONObject, typed step vs JSONObject).
export type MessageStartData = {
  strategyId?: string;
  strategy?: Strategy;
};
export type CitationsData = { citations?: Citation[] };
export type PlanningArtifactData = { planningArtifact?: PlanningArtifact };
export type ProblemFrameData = { problemFrame: ProblemFrame };
export type ToolCallStartData = { id: string; name: string; arguments: Record<string, unknown> };
export type ToolCallEndData = { id: string; result?: string | null };

export type StrategyUpdateStepData = {
  id: string;
  kind?: string | null;
  displayName?: string | null;
  searchName?: string | null;
  operator?: string | null;
  primaryInputStepId?: string | null;
  secondaryInputStepId?: string | null;
  parameters?: StepParameters | null;
  estimatedSize?: number | null;
  wdkStepId?: number | null;
  isBuilt?: boolean;
  isFiltered?: boolean;
  recordType?: string | null;
  name?: string | null;
  description?: string | null;
  graphId?: string | null;
  graphName?: string | null;
};

export type StrategyUpdateData = {
  graphId?: string;
  step?: StrategyUpdateStepData;
};

export type GraphSnapshotData = { graphSnapshot?: GraphSnapshotInput };
export type GraphPlanData = {
  graphId?: string;
  plan: StrategyPlan;
  name?: string;
  recordType?: string;
  description?: string;
};
export type PlanApprovedData = {
  planId: string;
  plan: Record<string, unknown>;
};
/**
 * message_end payload -- contents are unused but preserved for debugging.
 * Genuinely dynamic: the backend may include arbitrary diagnostic fields.
 */
export type MessageEndData = RawSSEData;
export type ErrorData = SSEErrorData;
export type WorkbenchGeneSetData = {
  geneSet?: {
    id?: string | null;
    name?: string | null;
    geneCount?: number | null;
    source?: string | null;
    siteId?: string | null;
  } | null;
};

/* ── Discriminated union ─────────────────────────────────────────────── */

import type {
  UserMessageData,
  AssistantDeltaData,
  AssistantMessageData,
  ModelSelectedData,
  TokenUsagePartialData,
  StrategyMetaData,
  StrategyLinkData,
  GraphClearedData,
  ReasoningData,
  PlanningThoughtData,
  PlanPresentedData,
  PlanUpdatedData,
  DecisionPresentedData,
  PhaseChangeData,
  OptimizationProgressData,
} from "@pathfinder/shared";

export type ChatSSEEvent =
  | { type: "message_start"; data: MessageStartData }
  | { type: "user_message"; data: UserMessageData }
  | { type: "assistant_delta"; data: AssistantDeltaData }
  | { type: "assistant_message"; data: AssistantMessageData }
  | { type: "citations"; data: CitationsData }
  | { type: "planning_artifact"; data: PlanningArtifactData }
  | { type: "problem_frame"; data: ProblemFrameData }
  | { type: "reasoning"; data: ReasoningData }
  | { type: "tool_call_start"; data: ToolCallStartData }
  | { type: "tool_call_end"; data: ToolCallEndData }
  | { type: "strategy_update"; data: StrategyUpdateData }
  | { type: "graph_snapshot"; data: GraphSnapshotData }
  | { type: "strategy_link"; data: StrategyLinkData }
  | { type: "strategy_meta"; data: StrategyMetaData }
  | { type: "graph_cleared"; data: GraphClearedData }
  | { type: "optimization_progress"; data: OptimizationProgressData }
  | { type: "model_selected"; data: ModelSelectedData }
  | { type: "graph_plan"; data: GraphPlanData }
  | { type: "token_usage_partial"; data: TokenUsagePartialData }
  | { type: "message_end"; data: MessageEndData }
  | { type: "error"; data: ErrorData }
  | { type: "workbench_gene_set"; data: WorkbenchGeneSetData }
  | { type: "planning_thought"; data: PlanningThoughtData }
  | { type: "plan_presented"; data: PlanPresentedData }
  | { type: "plan_approved"; data: PlanApprovedData }
  | { type: "plan_updated"; data: PlanUpdatedData }
  | { type: "decision_presented"; data: DecisionPresentedData }
  | { type: "phase_change"; data: PhaseChangeData }
  | { type: "unknown"; data: RawSSEData | string; rawType: string };
