import type {
  Citation,
  PlanningArtifact,
  OptimizationProgressData,
  Strategy,
} from "@pathfinder/shared";
import type { RawSSEEvent } from "@/lib/sse";
import type { GraphSnapshotInput, StepParameters } from "@/lib/strategyGraph/types";
import { isRecord } from "@/lib/utils/isRecord";
import { z } from "zod";

/**
 * Raw SSE event data before type-narrowing.
 * JSON-parsed payloads from the event stream are always string-keyed objects
 * with unknown values until narrowed by {@link parseChatSSEEvent}.
 */
export type RawSSEData = Record<string, unknown>;

/* ── Per-event data shapes ─────────────────────────────────────────── */

export type MessageStartData = {
  strategyId?: string;
  strategy?: Strategy;
  authToken?: string;
};
export type UserMessageData = { messageId?: string; content?: string };
export type AssistantDeltaData = { messageId?: string; delta?: string };
export type AssistantMessageData = { messageId?: string; content?: string };
export type CitationsData = { citations?: Citation[] };
export type PlanningArtifactData = { planningArtifact?: PlanningArtifact };
export type ReasoningData = { reasoning?: string };
export type ToolCallStartData = { id: string; name: string; arguments?: string };
export type ToolCallEndData = { id: string; result: string };
export type SubKaniTaskStartData = { task?: string };
export type SubKaniToolCallStartData = {
  task?: string;
  id: string;
  name: string;
  arguments?: string;
};
export type SubKaniToolCallEndData = { task?: string; id: string; result: string };
export type SubKaniTaskEndData = { task?: string; status?: string };

export type StrategyUpdateStepData = {
  stepId: string;
  kind?: string;
  displayName: string;
  searchName?: string;
  transformName?: string;
  operator?: string;
  primaryInputStepId?: string;
  secondaryInputStepId?: string;
  parameters?: StepParameters;
  name?: string | null;
  description?: string | null;
  recordType?: string;
  graphId?: string;
  graphName?: string;
};

export type StrategyUpdateData = {
  graphId?: string;
  step?: StrategyUpdateStepData;
};

export type GraphSnapshotData = { graphSnapshot?: GraphSnapshotInput };
export type StrategyLinkData = {
  graphId?: string;
  wdkStrategyId?: number;
  wdkUrl?: string;
  name?: string;
  description?: string;
};
export type StrategyMetaData = {
  graphId?: string;
  graphName?: string;
  name?: string;
  description?: string;
  recordType?: string | null;
};
export type GraphClearedData = { graphId?: string };
export type ModelSelectedData = { modelId: string };
export type GraphPlanData = {
  graphId?: string;
  plan: unknown;
  name?: string;
  recordType?: string;
  description?: string;
};
export type ExecutorBuildRequestData = { executorBuildRequest: unknown };
/**
 * message_end payload -- contents are unused but preserved for debugging.
 * Genuinely dynamic: the backend may include arbitrary diagnostic fields.
 */
export type MessageEndData = RawSSEData;
export type TokenUsagePartialData = {
  promptTokens?: number;
  registeredToolCount?: number;
};
export type ErrorData = { error: string };
export type WorkbenchGeneSetData = {
  geneSet?: {
    id: string;
    name: string;
    geneCount: number;
    source: string;
    siteId: string;
  };
};

/* ── Zod schemas for validated event data ─────────────────────────── */

const OptimizationTrialSchema = z
  .object({
    trialNumber: z.number(),
    parameters: z.record(z.string(), z.unknown()),
    score: z.number(),
    recall: z.number().nullable(),
    falsePositiveRate: z.number().nullable(),
    resultCount: z.number().nullable(),
    positiveHits: z.number().nullable(),
    negativeHits: z.number().nullable(),
    totalPositives: z.number().nullable(),
    totalNegatives: z.number().nullable(),
  })
  .passthrough();

const OptimizationParameterSpecSchema = z
  .object({
    name: z.string(),
    type: z.enum(["numeric", "integer", "categorical"]),
    minValue: z.number().nullable().optional(),
    maxValue: z.number().nullable().optional(),
    logScale: z.boolean().optional(),
    choices: z.array(z.string()).nullable().optional(),
  })
  .passthrough();

export const ToolCallStartDataSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    arguments: z.string().optional(),
  })
  .passthrough();

export const ToolCallEndDataSchema = z
  .object({
    id: z.string(),
    result: z.string(),
  })
  .passthrough();

export const SubKaniToolCallStartDataSchema = z
  .object({
    task: z.string().optional(),
    id: z.string(),
    name: z.string(),
    arguments: z.string().optional(),
  })
  .passthrough();

export const SubKaniToolCallEndDataSchema = z
  .object({
    task: z.string().optional(),
    id: z.string(),
    result: z.string(),
  })
  .passthrough();

export const OptimizationProgressDataSchema = z
  .object({
    optimizationId: z.string(),
    status: z.enum(["started", "running", "completed", "cancelled", "error"]),
    searchName: z.string().optional(),
    recordType: z.string().optional(),
    budget: z.number().optional(),
    objective: z.string().optional(),
    positiveControlsCount: z.number().optional(),
    negativeControlsCount: z.number().optional(),
    parameterSpace: z.array(OptimizationParameterSpecSchema).optional(),
    currentTrial: z.number().optional(),
    totalTrials: z.number().optional(),
    trial: OptimizationTrialSchema.optional(),
    bestTrial: OptimizationTrialSchema.nullable().optional(),
    recentTrials: z.array(OptimizationTrialSchema).optional(),
    allTrials: z.array(OptimizationTrialSchema).optional(),
    paretoFrontier: z.array(OptimizationTrialSchema).optional(),
    sensitivity: z.record(z.string(), z.number()).optional(),
    totalTimeSeconds: z.number().optional(),
    error: z.string().optional(),
  })
  .passthrough();

export const ModelSelectedDataSchema = z
  .object({
    modelId: z.string(),
  })
  .passthrough();

export const ErrorDataSchema = z
  .object({
    error: z.string(),
  })
  .passthrough();

/* ── Zod schemas for previously unvalidated event types ───────────── */

const StrategyUpdateStepDataSchema = z
  .object({
    stepId: z.string(),
    displayName: z.string(),
    kind: z.string().optional(),
    searchName: z.string().optional(),
    transformName: z.string().optional(),
    operator: z.string().optional(),
    primaryInputStepId: z.string().optional(),
    secondaryInputStepId: z.string().optional(),
    parameters: z.record(z.string(), z.unknown()).optional(),
    name: z.string().nullable().optional(),
    description: z.string().nullable().optional(),
    recordType: z.string().optional(),
    graphId: z.string().optional(),
    graphName: z.string().optional(),
  })
  .passthrough();

export const StrategyUpdateDataSchema = z
  .object({
    graphId: z.string().optional(),
    step: StrategyUpdateStepDataSchema.optional(),
  })
  .passthrough();

export const StrategyLinkDataSchema = z
  .object({
    graphId: z.string().optional(),
    wdkStrategyId: z.number().optional(),
    wdkUrl: z.string().optional(),
    name: z.string().optional(),
    description: z.string().optional(),
  })
  .passthrough();

export const StrategyMetaDataSchema = z
  .object({
    graphId: z.string().optional(),
    graphName: z.string().optional(),
    name: z.string().optional(),
    description: z.string().optional(),
    recordType: z.string().nullable().optional(),
  })
  .passthrough();

export const GraphPlanDataSchema = z
  .object({
    graphId: z.string().optional(),
    plan: z.unknown(),
    name: z.string().optional(),
    recordType: z.string().optional(),
    description: z.string().optional(),
  })
  .passthrough();

const WorkbenchGeneSetInnerSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    geneCount: z.number(),
    source: z.string(),
    siteId: z.string(),
  })
  .passthrough();

export const WorkbenchGeneSetDataSchema = z
  .object({
    geneSet: WorkbenchGeneSetInnerSchema.optional(),
  })
  .passthrough();

/* ── Discriminated union ───────────────────────────────────────────── */

export type ChatSSEEvent =
  | { type: "message_start"; data: MessageStartData }
  | { type: "user_message"; data: UserMessageData }
  | { type: "assistant_delta"; data: AssistantDeltaData }
  | { type: "assistant_message"; data: AssistantMessageData }
  | { type: "citations"; data: CitationsData }
  | { type: "planning_artifact"; data: PlanningArtifactData }
  | { type: "reasoning"; data: ReasoningData }
  | { type: "tool_call_start"; data: ToolCallStartData }
  | { type: "tool_call_end"; data: ToolCallEndData }
  | { type: "subkani_task_start"; data: SubKaniTaskStartData }
  | { type: "subkani_tool_call_start"; data: SubKaniToolCallStartData }
  | { type: "subkani_tool_call_end"; data: SubKaniToolCallEndData }
  | { type: "subkani_task_end"; data: SubKaniTaskEndData }
  | { type: "strategy_update"; data: StrategyUpdateData }
  | { type: "graph_snapshot"; data: GraphSnapshotData }
  | { type: "strategy_link"; data: StrategyLinkData }
  | { type: "strategy_meta"; data: StrategyMetaData }
  | { type: "graph_cleared"; data: GraphClearedData }
  | { type: "optimization_progress"; data: OptimizationProgressData }
  | { type: "model_selected"; data: ModelSelectedData }
  | { type: "graph_plan"; data: GraphPlanData }
  | { type: "executor_build_request"; data: ExecutorBuildRequestData }
  | { type: "token_usage_partial"; data: TokenUsagePartialData }
  | { type: "message_end"; data: MessageEndData }
  | { type: "error"; data: ErrorData }
  | { type: "workbench_gene_set"; data: WorkbenchGeneSetData }
  | { type: "unknown"; data: RawSSEData | string; rawType: string };

/** Extract the data type for a specific event type from the discriminated union. */
export type ChatSSEEventData<T extends ChatSSEEvent["type"]> = Extract<
  ChatSSEEvent,
  { type: T }
>["data"];

/* ── Parsing helpers ───────────────────────────────────────────────── */

function safeJsonParse(text: string): RawSSEData | string {
  try {
    const parsed = JSON.parse(text);
    return isRecord(parsed) ? parsed : text;
  } catch {
    return text;
  }
}

/**
 * Validate that parsed data is a non-null object (not an array or string).
 * Returns the data as a Record, or null if invalid.
 */
function asRecord(data: unknown): RawSSEData | null {
  return isRecord(data) ? data : null;
}

/* ── Per-event-type narrowing ──────────────────────────────────────── */

/**
 * Try to parse `data` with a Zod schema.
 * Returns the parsed result on success, or null on failure (with a warning).
 */
function zodNarrow<T>(schema: z.ZodType<T>, type: string, data: RawSSEData): T | null {
  const result = schema.safeParse(data);
  if (result.success) return result.data;
  console.warn(`[SSE] ${type} failed validation:`, result.error.issues, data);
  return null;
}

/**
 * Narrow a raw SSE event into a typed ChatSSEEvent.
 *
 * Returns:
 * - A `ChatSSEEvent` on success
 * - `null` if the type is known but the data is malformed (caller should skip)
 * - `undefined` if the type is unrecognized (caller should wrap as "unknown")
 */
function narrowEventData(
  type: string,
  data: RawSSEData,
): ChatSSEEvent | null | undefined {
  switch (type) {
    // All-optional fields: passthrough is safe — the data is already a record.
    case "message_start":
      return { type, data: data as MessageStartData };

    case "user_message":
      return { type, data: data as UserMessageData };

    case "assistant_delta":
      return { type, data: data as AssistantDeltaData };

    case "assistant_message":
      return { type, data: data as AssistantMessageData };

    case "citations":
      return { type, data: data as CitationsData };

    case "planning_artifact":
      return { type, data: data as PlanningArtifactData };

    case "reasoning":
      return { type, data: data as ReasoningData };

    case "subkani_task_start":
      return { type, data: data as SubKaniTaskStartData };

    case "subkani_task_end":
      return { type, data: data as SubKaniTaskEndData };

    case "graph_snapshot":
      return { type, data: data as GraphSnapshotData };

    case "graph_cleared":
      return { type, data: data as GraphClearedData };

    case "executor_build_request":
      return { type, data: data as ExecutorBuildRequestData };

    case "token_usage_partial":
      return { type, data: data as TokenUsagePartialData };

    case "message_end":
      return { type, data: data as MessageEndData };

    // Validated via Zod: events with required fields or complex nested structures.
    case "tool_call_start": {
      const parsed = zodNarrow(ToolCallStartDataSchema, type, data);
      return parsed ? { type, data: parsed } : null;
    }

    case "tool_call_end": {
      const parsed = zodNarrow(ToolCallEndDataSchema, type, data);
      return parsed ? { type, data: parsed } : null;
    }

    case "subkani_tool_call_start": {
      const parsed = zodNarrow(SubKaniToolCallStartDataSchema, type, data);
      return parsed ? { type, data: parsed } : null;
    }

    case "subkani_tool_call_end": {
      const parsed = zodNarrow(SubKaniToolCallEndDataSchema, type, data);
      return parsed ? { type, data: parsed } : null;
    }

    case "optimization_progress": {
      const parsed = zodNarrow(OptimizationProgressDataSchema, type, data);
      return parsed ? { type, data: parsed } : null;
    }

    case "model_selected": {
      const parsed = zodNarrow(ModelSelectedDataSchema, type, data);
      return parsed ? { type, data: parsed } : null;
    }

    case "error": {
      const parsed = zodNarrow(ErrorDataSchema, type, data);
      return parsed ? { type, data: parsed } : null;
    }

    case "strategy_update": {
      const parsed = zodNarrow(StrategyUpdateDataSchema, type, data);
      return parsed ? { type, data: parsed } : null;
    }

    case "strategy_link": {
      const parsed = zodNarrow(StrategyLinkDataSchema, type, data);
      return parsed ? { type, data: parsed } : null;
    }

    case "strategy_meta": {
      const parsed = zodNarrow(StrategyMetaDataSchema, type, data);
      return parsed ? { type, data: parsed } : null;
    }

    case "graph_plan": {
      const parsed = zodNarrow(GraphPlanDataSchema, type, data);
      return parsed ? { type, data: parsed } : null;
    }

    case "workbench_gene_set": {
      const parsed = zodNarrow(WorkbenchGeneSetDataSchema, type, data);
      return parsed ? { type, data: parsed } : null;
    }

    default:
      return undefined;
  }
}

/* ── Public API ────────────────────────────────────────────────────── */

export function parseChatSSEEvent(
  event: RawSSEEvent | { type: string; data: RawSSEData },
): ChatSSEEvent | null {
  const data = typeof event.data === "string" ? safeJsonParse(event.data) : event.data;
  const type = event.type;

  // Non-object payloads can only be represented as "unknown" events.
  const rec = asRecord(data);
  if (!rec) {
    console.warn(`[SSE] Event "${type}" has non-object data, skipping:`, data);
    return {
      type: "unknown",
      rawType: type,
      data: typeof data === "string" ? data : {},
    };
  }

  const narrowed = narrowEventData(type, rec);

  // Validated successfully — return the typed event.
  if (narrowed) return narrowed;

  // Known event type but data validation failed — skip (null).
  if (narrowed === null) return null;

  // Unrecognized event type — wrap as "unknown" for forward compatibility.
  if (type !== "unknown") {
    console.warn(`[SSE] Unrecognized event type "${type}", skipping.`);
  }
  return { type: "unknown", rawType: type, data: rec };
}
