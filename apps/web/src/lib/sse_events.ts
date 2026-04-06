/**
 * SSE event parsing — barrel re-exports + parse logic.
 *
 * Types live in `./sse_events.types`, Zod schemas in `./sse_events.schemas`.
 * This file re-exports everything so existing `@/lib/sse_events` imports
 * continue to work unchanged.
 */

import type { RawSSEEvent } from "@/lib/sse";
import type {
  RawSSEData, ChatSSEEvent, MessageStartData, CitationsData,
  PlanningArtifactData, ToolCallStartData, ToolCallEndData,
  StrategyUpdateData, GraphSnapshotData, GraphPlanData,
  WorkbenchGeneSetData, ErrorData,
} from "./sse_events.types";
import type {
  UserMessageData, AssistantDeltaData, AssistantMessageData,
  ModelSelectedData, TokenUsagePartialData, StrategyMetaData,
  StrategyLinkData, GraphClearedData, ReasoningData,
  PlanningThoughtData, PlanPresentedData, PlanUpdatedData,
  DecisionPresentedData, PhaseChangeData, OptimizationProgressData,
} from "@pathfinder/shared";
import {
  ToolCallStartDataSchema, ToolCallEndDataSchema,
  OptimizationProgressDataSchema, ModelSelectedDataSchema, ErrorDataSchema,
  StrategyUpdateDataSchema, StrategyLinkDataSchema, StrategyMetaDataSchema,
  GraphPlanDataSchema, WorkbenchGeneSetDataSchema,
  PlanningThoughtDataSchema, PlanPresentedDataSchema, PlanUpdatedDataSchema,
  DecisionPresentedDataSchema, PhaseChangeDataSchema,
} from "./sse_events.schemas";
import { isRecord } from "@/lib/utils/isRecord";
import { z } from "zod";

/* ── Re-exports: types ───────────────────────────────────────────────── */
export type {
  RawSSEData, MessageStartData, CitationsData, PlanningArtifactData,
  ToolCallStartData, ToolCallEndData, StrategyUpdateStepData,
  StrategyUpdateData, GraphSnapshotData, GraphPlanData, MessageEndData,
  ErrorData, WorkbenchGeneSetData, ChatSSEEvent,
  UserMessageData, AssistantDeltaData, AssistantMessageData,
  ModelSelectedData, TokenUsagePartialData, StrategyMetaData,
  StrategyLinkData, GraphClearedData, ReasoningData,
  PlanningThoughtData, PlanPresentedData, PlanUpdatedData,
  DecisionPresentedData, PhaseChangeData, OptimizationProgressData,
} from "./sse_events.types";

/* ── Re-exports: schemas ─────────────────────────────────────────────── */
export {
  ToolCallStartDataSchema, ToolCallEndDataSchema,
  OptimizationProgressDataSchema, ModelSelectedDataSchema, ErrorDataSchema,
  StrategyUpdateDataSchema, StrategyLinkDataSchema, StrategyMetaDataSchema,
  GraphPlanDataSchema, WorkbenchGeneSetDataSchema,
  PlanningThoughtDataSchema, PlanPresentedDataSchema, PlanUpdatedDataSchema,
  DecisionPresentedDataSchema, PhaseChangeDataSchema,
} from "./sse_events.schemas";

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
    case "planning_thought": {
      const d = zodNarrow<PlanningThoughtData>(PlanningThoughtDataSchema, type, data);
      return d != null ? { type, data: d } : null;
    }
    case "plan_presented": {
      const d = zodNarrow<PlanPresentedData>(PlanPresentedDataSchema, type, data);
      return d != null ? { type, data: d } : null;
    }
    case "plan_updated": {
      const d = zodNarrow<PlanUpdatedData>(PlanUpdatedDataSchema, type, data);
      return d != null ? { type, data: d } : null;
    }
    case "decision_presented": {
      const d = zodNarrow<DecisionPresentedData>(DecisionPresentedDataSchema, type, data);
      return d != null ? { type, data: d } : null;
    }
    case "phase_change": {
      const d = zodNarrow<PhaseChangeData>(PhaseChangeDataSchema, type, data);
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
