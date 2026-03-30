import type {
  Citation,
  PlanningArtifact,
  OptimizationProgressData,
  Strategy,
  StrategyPlan,
  UserMessageData,
  AssistantDeltaData,
  AssistantMessageData,
  SubKaniTaskStartData,
  SubKaniTaskEndData,
  SubKaniToolCallStartData,
  SubKaniToolCallEndData,
  ModelSelectedData,
  TokenUsagePartialData,
  StrategyMetaData,
  StrategyLinkData,
  GraphClearedData,
  ReasoningData,
  SSEErrorData,
} from "@pathfinder/shared";
export type {
  UserMessageData,
  AssistantDeltaData,
  AssistantMessageData,
  SubKaniTaskStartData,
  SubKaniTaskEndData,
  SubKaniToolCallStartData,
  SubKaniToolCallEndData,
  ModelSelectedData,
  TokenUsagePartialData,
  StrategyMetaData,
  StrategyLinkData,
  GraphClearedData,
  ReasoningData,
} from "@pathfinder/shared";

/** Data for subkani_task_retry events (not yet in OpenAPI spec). */
export type SubKaniTaskRetryData = {
  task?: string | null;
  attempt?: number | null;
};
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
// Types that remain local — their local shapes differ from the generated
// equivalents (e.g., typed strategy vs JSONObject, typed step vs JSONObject).
export type MessageStartData = {
  strategyId?: string;
  strategy?: Strategy;
};
export type CitationsData = { citations?: Citation[] };
export type PlanningArtifactData = { planningArtifact?: PlanningArtifact };
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

/* ── Zod schemas for validated event data ─────────────────────────── */

const OptimizationTrialSchema = z
  .object({
    trialNumber: z.number(),
    parameters: z.record(z.string(), z.unknown()).optional(),
    score: z.number(),
    recall: z.number().nullable().optional(),
    falsePositiveRate: z.number().nullable().optional(),
    estimatedSize: z.number().nullable().optional(),
    positiveHits: z.number().nullable().optional(),
    negativeHits: z.number().nullable().optional(),
    totalPositives: z.number().nullable().optional(),
    totalNegatives: z.number().nullable().optional(),
  })
  .passthrough();

const OptimizationParameterSpecSchema = z
  .object({
    name: z.string(),
    type: z.enum(["numeric", "integer", "categorical"]),
    minValue: z.number().nullable().optional(),
    maxValue: z.number().nullable().optional(),
    logScale: z.boolean().nullable().optional(),
    choices: z.array(z.string()).nullable().optional(),
  })
  .passthrough();

export const ToolCallStartDataSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    arguments: z.record(z.string(), z.unknown()).default({}),
  })
  .passthrough();

export const ToolCallEndDataSchema = z
  .object({
    id: z.string(),
    result: z.string().nullish(),
  })
  .passthrough();

export const SubKaniToolCallStartDataSchema = z
  .object({
    task: z.string().nullish(),
    id: z.string(),
    name: z.string(),
    arguments: z.record(z.string(), z.unknown()).default({}),
  })
  .passthrough();

export const SubKaniToolCallEndDataSchema = z
  .object({
    task: z.string().nullish(),
    id: z.string(),
    result: z.string().nullable(),
  })
  .passthrough();

export const SubKaniTaskRetryDataSchema = z
  .object({
    task: z.string().nullish(),
    attempt: z.number().nullish(),
  })
  .passthrough();

export const OptimizationProgressDataSchema = z
  .object({
    optimizationId: z.string(),
    status: z.enum(["started", "running", "completed", "cancelled", "error"]),
    searchName: z.string().nullish(),
    recordType: z.string().nullish(),
    budget: z.number().nullish(),
    objective: z.string().nullish(),
    positiveControlsCount: z.number().nullish(),
    negativeControlsCount: z.number().nullish(),
    parameterSpecs: z.array(OptimizationParameterSpecSchema).nullish(),
    currentTrial: z.number().nullish(),
    totalTrials: z.number().nullish(),
    trial: OptimizationTrialSchema.nullish(),
    bestTrial: OptimizationTrialSchema.nullable().optional(),
    recentTrials: z.array(OptimizationTrialSchema).nullish(),
    allTrials: z.array(OptimizationTrialSchema).nullish(),
    paretoFrontier: z.array(OptimizationTrialSchema).nullish(),
    sensitivity: z.record(z.string(), z.number()).nullish(),
    totalTimeSeconds: z.number().nullish(),
    error: z.string().nullish(),
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
    id: z.string(),
    kind: z.string().nullish(),
    displayName: z.string().nullish(),
    searchName: z.string().nullish(),
    operator: z.string().nullish(),
    primaryInputStepId: z.string().nullish(),
    secondaryInputStepId: z.string().nullish(),
    parameters: z.record(z.string(), z.unknown()).nullish(),
    estimatedSize: z.number().nullish(),
    wdkStepId: z.number().nullish(),
    isBuilt: z.boolean().optional(),
    isFiltered: z.boolean().optional(),
    recordType: z.string().nullish(),
    name: z.string().nullish(),
    description: z.string().nullish(),
    graphId: z.string().nullish(),
    graphName: z.string().nullish(),
  })
  .passthrough();

export const StrategyUpdateDataSchema = z
  .object({
    graphId: z.string().nullish(),
    step: StrategyUpdateStepDataSchema.nullish(),
  })
  .passthrough();

export const StrategyLinkDataSchema = z
  .object({
    graphId: z.string().nullish(),
    wdkStrategyId: z.number().nullish(),
    wdkUrl: z.string().nullish(),
    name: z.string().nullish(),
    description: z.string().nullish(),
    isSaved: z.boolean().nullish(),
  })
  .passthrough();

export const StrategyMetaDataSchema = z
  .object({
    graphId: z.string().nullish(),
    graphName: z.string().nullish(),
    name: z.string().nullish(),
    description: z.string().nullish(),
    recordType: z.string().nullable().optional(),
  })
  .passthrough();

export const GraphPlanDataSchema = z
  .object({
    graphId: z.string().nullish(),
    plan: z.unknown(),
    name: z.string().nullish(),
    recordType: z.string().nullish(),
    description: z.string().nullish(),
  })
  .passthrough();

const WorkbenchGeneSetInnerSchema = z
  .object({
    id: z.string().nullish(),
    name: z.string().nullish(),
    geneCount: z.number().nullish(),
    source: z.string().nullish(),
    siteId: z.string().nullish(),
  })
  .passthrough();

export const WorkbenchGeneSetDataSchema = z
  .object({
    geneSet: WorkbenchGeneSetInnerSchema.nullish(),
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
  | { type: "subkani_task_retry"; data: SubKaniTaskRetryData }
  | { type: "subkani_task_end"; data: SubKaniTaskEndData }
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
  | { type: "unknown"; data: RawSSEData | string; rawType: string };

/* ── Parsing helpers ───────────────────────────────────────────────── */

function safeJsonParse(text: string): RawSSEData | string {
  try {
    const parsed: unknown = JSON.parse(text);
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
 * Try to parse `data` with a Zod schema and cast to the target type.
 *
 * Zod's `.passthrough()` adds `[x: string]: unknown` to the inferred type,
 * which makes optional `.nullish()` fields include `| undefined`.  With
 * `exactOptionalPropertyTypes` this is incompatible with target types that
 * use `T | null` (no undefined).  The cast via `Target` strips the index
 * signature after Zod has validated the data.
 */
function zodNarrow<Target>(
  schema: z.ZodType<unknown>,
  type: string,
  data: RawSSEData,
): Target | null {
  const result = schema.safeParse(data);
  if (result.success) return result.data as Target;
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

    case "subkani_task_retry": {
      const d = zodNarrow<SubKaniTaskRetryData>(SubKaniTaskRetryDataSchema, type, data);
      return d != null ? { type, data: d } : null;
    }

    case "graph_snapshot":
      return { type, data: data as GraphSnapshotData };

    case "graph_cleared":
      return { type, data: data as GraphClearedData };

    case "token_usage_partial":
      return { type, data: data as TokenUsagePartialData };

    case "message_end":
      return { type, data };

    // Validated via Zod: events with required fields or complex nested structures.
    case "tool_call_start": {
      const d = zodNarrow<ToolCallStartData>(ToolCallStartDataSchema, type, data);
      return d != null ? { type, data: d } : null;
    }
    case "tool_call_end": {
      const d = zodNarrow<ToolCallEndData>(ToolCallEndDataSchema, type, data);
      return d != null ? { type, data: d } : null;
    }
    case "subkani_tool_call_start": {
      const d = zodNarrow<SubKaniToolCallStartData>(
        SubKaniToolCallStartDataSchema,
        type,
        data,
      );
      return d != null ? { type, data: d } : null;
    }
    case "subkani_tool_call_end": {
      const d = zodNarrow<SubKaniToolCallEndData>(
        SubKaniToolCallEndDataSchema,
        type,
        data,
      );
      return d != null ? { type, data: d } : null;
    }
    case "optimization_progress": {
      const d = zodNarrow<OptimizationProgressData>(
        OptimizationProgressDataSchema,
        type,
        data,
      );
      return d != null ? { type, data: d } : null;
    }
    case "model_selected": {
      const d = zodNarrow<ModelSelectedData>(ModelSelectedDataSchema, type, data);
      return d != null ? { type, data: d } : null;
    }
    case "error": {
      const d = zodNarrow<ErrorData>(ErrorDataSchema, type, data);
      return d != null ? { type, data: d } : null;
    }
    case "strategy_update": {
      const d = zodNarrow<StrategyUpdateData>(StrategyUpdateDataSchema, type, data);
      return d != null ? { type, data: d } : null;
    }
    case "strategy_link": {
      const d = zodNarrow<StrategyLinkData>(StrategyLinkDataSchema, type, data);
      return d != null ? { type, data: d } : null;
    }
    case "strategy_meta": {
      const d = zodNarrow<StrategyMetaData>(StrategyMetaDataSchema, type, data);
      return d != null ? { type, data: d } : null;
    }
    case "graph_plan": {
      const d = zodNarrow<GraphPlanData>(GraphPlanDataSchema, type, data);
      return d != null ? { type, data: d } : null;
    }
    case "workbench_gene_set": {
      const d = zodNarrow<WorkbenchGeneSetData>(WorkbenchGeneSetDataSchema, type, data);
      return d != null ? { type, data: d } : null;
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
