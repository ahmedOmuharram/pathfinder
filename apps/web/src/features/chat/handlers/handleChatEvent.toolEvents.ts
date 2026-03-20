import type { ToolCall } from "@pathfinder/shared";
import type { ChatEventContext } from "./handleChatEvent.types";
import type {
  ToolCallStartData,
  ToolCallEndData,
  SubKaniTaskStartData,
  SubKaniToolCallStartData,
  SubKaniToolCallEndData,
  SubKaniTaskEndData,
} from "@/lib/sse_events";

export function handleToolCallStartEvent(
  ctx: ChatEventContext,
  data: ToolCallStartData,
) {
  const { id, name, arguments: args } = data;
  const newToolCall: ToolCall = { id, name, arguments: ctx.parseToolArguments(args) };
  ctx.toolCallsBuffer.push(newToolCall);
  ctx.thinking.updateActiveFromBuffer([...ctx.toolCallsBuffer]);
}

export function handleToolCallEndEvent(ctx: ChatEventContext, data: ToolCallEndData) {
  const { id, result } = data;
  const tc = ctx.toolCallsBuffer.find((t) => t.id === id);
  if (tc) {
    tc.result = result;
    ctx.thinking.updateActiveFromBuffer([...ctx.toolCallsBuffer]);
  }
  const parsed = ctx.parseToolResult(result);
  const snapshot = parsed?.graphSnapshot;
  if (snapshot != null && typeof snapshot === "object" && !Array.isArray(snapshot)) {
    ctx.applyGraphSnapshot(snapshot);
  }
}

export function handleSubKaniTaskStartEvent(
  ctx: ChatEventContext,
  data: SubKaniTaskStartData,
) {
  const { task } = data;
  if (task == null || task === "") return;
  ctx.thinking.subKaniTaskStart(task, data.modelId ?? undefined);
  ctx.subKaniStatusBuffer[task] = "running";
  ctx.subKaniCallsBuffer[task] = ctx.subKaniCallsBuffer[task] ?? [];
  if (data.modelId != null && data.modelId !== "")
    ctx.subKaniModelsBuffer[task] = data.modelId;
}

export function handleSubKaniToolCallStartEvent(
  ctx: ChatEventContext,
  data: SubKaniToolCallStartData,
) {
  const { task, id, name, arguments: args } = data;
  if (task == null || task === "") return;
  const newToolCall: ToolCall = { id, name, arguments: ctx.parseToolArguments(args) };
  ctx.thinking.subKaniToolCallStart(task, newToolCall);
  const taskCalls = ctx.subKaniCallsBuffer[task] ?? [];
  taskCalls.push(newToolCall);
  ctx.subKaniCallsBuffer[task] = taskCalls;
}

export function handleSubKaniToolCallEndEvent(
  ctx: ChatEventContext,
  data: SubKaniToolCallEndData,
) {
  const { task, id, result } = data;
  if (task == null || task === "") return;
  ctx.thinking.subKaniToolCallEnd(task, id, result ?? "");
  const taskCalls = ctx.subKaniCallsBuffer[task];
  if (taskCalls) {
    const call = taskCalls.find((c) => c.id === id);
    if (call) call.result = result ?? null;
  }
}

export function handleSubKaniTaskEndEvent(
  ctx: ChatEventContext,
  data: SubKaniTaskEndData,
) {
  const { task, status } = data;
  if (task == null || task === "") return;
  ctx.thinking.subKaniTaskEnd(task, status ?? undefined);
  ctx.subKaniStatusBuffer[task] = status ?? "done";
  if (data.promptTokens != null) {
    ctx.subKaniTokenUsageBuffer[task] = {
      promptTokens: data.promptTokens ?? 0,
      completionTokens: data.completionTokens ?? 0,
      llmCallCount: data.llmCallCount ?? 0,
      estimatedCostUsd: data.estimatedCostUsd ?? 0,
    };
  }
}
