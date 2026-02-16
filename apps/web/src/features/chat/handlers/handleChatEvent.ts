import type { ChatSSEEvent } from "@/features/chat/sse_events";
import type { ChatEventContext } from "./handleChatEvent.types";
import {
  handleAssistantDeltaEvent,
  handleAssistantMessageEvent,
  handleCitationsEvent,
  handleErrorEvent,
  handleExecutorBuildRequestEvent,
  handleMessageStartEvent,
  handleOptimizationProgressEvent,
  handlePlanningArtifactEvent,
  handlePlanUpdateEvent,
  handleReasoningEvent,
} from "./handleChatEvent.messageEvents";
import {
  handleGraphSnapshotEvent,
  handleStrategyClearedEvent,
  handleStrategyLinkEvent,
  handleStrategyMetaEvent,
  handleStrategyUpdateEvent,
} from "./handleChatEvent.strategyEvents";
import {
  handleSubKaniTaskEndEvent,
  handleSubKaniTaskStartEvent,
  handleSubKaniToolCallEndEvent,
  handleSubKaniToolCallStartEvent,
  handleToolCallEndEvent,
  handleToolCallStartEvent,
} from "./handleChatEvent.toolEvents";
export type { ChatEventContext } from "./handleChatEvent.types";

export function handleChatEvent(ctx: ChatEventContext, event: ChatSSEEvent) {
  switch (event.type) {
    case "message_start": {
      handleMessageStartEvent(ctx, event.data);
      break;
    }
    case "assistant_delta": {
      handleAssistantDeltaEvent(ctx, event.data);
      break;
    }
    case "assistant_message": {
      handleAssistantMessageEvent(ctx, event.data);
      break;
    }
    case "citations": {
      handleCitationsEvent(ctx, event.data);
      break;
    }
    case "planning_artifact": {
      handlePlanningArtifactEvent(ctx, event.data);
      break;
    }
    case "reasoning": {
      handleReasoningEvent(ctx, event.data);
      break;
    }
    case "tool_call_start": {
      handleToolCallStartEvent(ctx, event.data);
      break;
    }
    case "tool_call_end": {
      handleToolCallEndEvent(ctx, event.data);
      break;
    }
    case "subkani_task_start": {
      handleSubKaniTaskStartEvent(ctx, event.data);
      break;
    }
    case "subkani_tool_call_start": {
      handleSubKaniToolCallStartEvent(ctx, event.data);
      break;
    }
    case "subkani_tool_call_end": {
      handleSubKaniToolCallEndEvent(ctx, event.data);
      break;
    }
    case "subkani_task_end": {
      handleSubKaniTaskEndEvent(ctx, event.data);
      break;
    }
    case "strategy_update": {
      handleStrategyUpdateEvent(ctx, event.data);
      break;
    }
    case "graph_snapshot": {
      handleGraphSnapshotEvent(ctx, event.data);
      break;
    }
    case "strategy_link": {
      handleStrategyLinkEvent(ctx, event.data);
      break;
    }
    case "strategy_meta": {
      handleStrategyMetaEvent(ctx, event.data);
      break;
    }
    case "strategy_cleared": {
      handleStrategyClearedEvent(ctx, event.data);
      break;
    }
    case "executor_build_request": {
      handleExecutorBuildRequestEvent(ctx, event.data);
      break;
    }
    case "optimization_progress": {
      handleOptimizationProgressEvent(ctx, event.data);
      break;
    }
    case "plan_update": {
      handlePlanUpdateEvent(ctx, event.data);
      break;
    }
    case "error": {
      handleErrorEvent(ctx, event.data);
      break;
    }
    case "unknown":
    default:
      break;
  }
}
