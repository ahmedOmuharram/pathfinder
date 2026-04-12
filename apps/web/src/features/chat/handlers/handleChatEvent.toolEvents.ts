import type { ToolCall } from "@pathfinder/shared";
import type {
  StreamBuffers,
  StreamContext,
  EventHelpers,
} from "./handleChatEvent.types";
import type {
  ToolCallStartData,
  ToolCallEndData,
} from "@/lib/sse_events";

type ToolEventContext =
  & StreamBuffers
  & Pick<StreamContext, "thinking" | "streamState">
  & Pick<EventHelpers, "parseToolArguments" | "parseToolResult" | "applyGraphSnapshot">;

export function handleToolCallStartEvent(
  ctx: ToolEventContext,
  data: ToolCallStartData,
) {
  const { id, name, arguments: args } = data;
  const newToolCall: ToolCall = { id, name, arguments: ctx.parseToolArguments(args) };
  ctx.toolCallsBuffer.push(newToolCall);
  ctx.thinking.updateActiveFromBuffer(
    [...ctx.toolCallsBuffer],
    ctx.streamState.streamingAssistantMessageId,
  );
}

export function handleToolCallEndEvent(ctx: ToolEventContext, data: ToolCallEndData) {
  const { id, result } = data;
  const tc = ctx.toolCallsBuffer.find((t) => t.id === id);
  if (tc) {
    tc.result = result ?? null;
    ctx.thinking.updateActiveFromBuffer(
      [...ctx.toolCallsBuffer],
      ctx.streamState.streamingAssistantMessageId,
    );
  }
  const parsed = ctx.parseToolResult(result ?? null);
  const snapshot = parsed?.graphSnapshot;
  if (snapshot != null && typeof snapshot === "object" && !Array.isArray(snapshot)) {
    ctx.applyGraphSnapshot(snapshot);
  }
}
