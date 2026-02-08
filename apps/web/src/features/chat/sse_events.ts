import type { Message, ToolCall, Citation, PlanningArtifact } from "@pathfinder/shared";
import type { StrategyWithMeta } from "@/types/strategy";
import type { RawSSEEvent } from "@/lib/sse";

export type ChatSSEEvent =
  | {
      type: "message_start";
      data: {
        strategyId?: string;
        strategy?: StrategyWithMeta;
        planSessionId?: string;
        planSession?: Record<string, unknown>;
        authToken?: string;
      };
    }
  | { type: "assistant_delta"; data: { messageId?: string; delta?: string } }
  | { type: "assistant_message"; data: { messageId?: string; content?: string } }
  | { type: "citations"; data: { citations?: Citation[] } }
  | { type: "planning_artifact"; data: { planningArtifact?: PlanningArtifact } }
  | {
      type: "executor_build_request";
      data: { executorBuildRequest?: Record<string, unknown> };
    }
  | { type: "reasoning"; data: { reasoning?: string } }
  | { type: "plan_update"; data: { title?: string } }
  | { type: "tool_call_start"; data: { id: string; name: string; arguments?: string } }
  | { type: "tool_call_end"; data: { id: string; result: string } }
  | { type: "subkani_task_start"; data: { task?: string } }
  | {
      type: "subkani_tool_call_start";
      data: { task?: string; id: string; name: string; arguments?: string };
    }
  | {
      type: "subkani_tool_call_end";
      data: { task?: string; id: string; result: string };
    }
  | { type: "subkani_task_end"; data: { task?: string; status?: string } }
  | { type: "strategy_update"; data: Record<string, unknown> }
  | { type: "graph_snapshot"; data: { graphSnapshot?: Record<string, unknown> } }
  | {
      type: "strategy_link";
      data: {
        graphId?: string;
        strategySnapshotId?: string;
        wdkStrategyId?: number;
        wdkUrl?: string;
        name?: string;
        description?: string;
      };
    }
  | {
      type: "strategy_meta";
      data: {
        graphId?: string;
        graphName?: string;
        name?: string;
        description?: string;
        recordType?: string | null;
      };
    }
  | { type: "strategy_cleared"; data: { graphId?: string } }
  | { type: "error"; data: { error: string } }
  | { type: "unknown"; data: Record<string, unknown> | string; rawType: string };

function safeJsonParse(text: string): Record<string, unknown> | string {
  try {
    const parsed = JSON.parse(text);
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : text;
  } catch {
    return text;
  }
}

export function parseChatSSEEvent(event: RawSSEEvent): ChatSSEEvent {
  const data = safeJsonParse(event.data);
  const type = event.type;

  switch (type) {
    case "message_start":
    case "assistant_delta":
    case "assistant_message":
    case "citations":
    case "planning_artifact":
    case "executor_build_request":
    case "reasoning":
    case "plan_update":
    case "tool_call_start":
    case "tool_call_end":
    case "subkani_task_start":
    case "subkani_tool_call_start":
    case "subkani_tool_call_end":
    case "subkani_task_end":
    case "strategy_update":
    case "graph_snapshot":
    case "strategy_link":
    case "strategy_meta":
    case "strategy_cleared":
    case "error":
      return { type, data } as ChatSSEEvent;
    default:
      return {
        type: "unknown",
        rawType: type,
        data,
      };
  }
}

// Convenience: these are only used for typing in UI code.
export type ChatMessage = Message;
export type ChatToolCall = ToolCall;
