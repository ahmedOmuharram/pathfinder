import type { ToolCall } from "@pathfinder/shared";
import type { ChatEventContext } from "./handleChatEvent.types";

export function handleToolCallStartEvent(ctx: ChatEventContext, data: unknown) {
  const {
    id,
    name,
    arguments: args,
  } = data as {
    id: string;
    name: string;
    arguments?: string;
  };
  const newToolCall: ToolCall = { id, name, arguments: ctx.parseToolArguments(args) };
  ctx.toolCallsBuffer.push(newToolCall);
  ctx.thinking.updateActiveFromBuffer([...ctx.toolCallsBuffer]);
}

export function handleToolCallEndEvent(ctx: ChatEventContext, data: unknown) {
  const { id, result } = data as { id: string; result: string };
  const tc = ctx.toolCallsBuffer.find((t) => t.id === id);
  if (tc) {
    tc.result = result;
    ctx.thinking.updateActiveFromBuffer([...ctx.toolCallsBuffer]);
  }
  const parsed = ctx.parseToolResult(result);
  const snapshot = parsed?.graphSnapshot;
  if (snapshot && typeof snapshot === "object" && !Array.isArray(snapshot)) {
    ctx.applyGraphSnapshot(snapshot);
  }
}

export function handleSubKaniTaskStartEvent(ctx: ChatEventContext, data: unknown) {
  const { task } = data as { task?: string };
  if (task) ctx.thinking.subKaniTaskStart(task);
}

export function handleSubKaniToolCallStartEvent(ctx: ChatEventContext, data: unknown) {
  const {
    task,
    id,
    name,
    arguments: args,
  } = data as {
    task?: string;
    id: string;
    name: string;
    arguments?: string;
  };
  if (!task) return;
  const newToolCall: ToolCall = { id, name, arguments: ctx.parseToolArguments(args) };
  ctx.thinking.subKaniToolCallStart(task, newToolCall);
}

export function handleSubKaniToolCallEndEvent(ctx: ChatEventContext, data: unknown) {
  const { task, id, result } = data as {
    task?: string;
    id: string;
    result: string;
  };
  if (!task) return;
  ctx.thinking.subKaniToolCallEnd(task, id, result);
}

export function handleSubKaniTaskEndEvent(ctx: ChatEventContext, data: unknown) {
  const { task, status } = data as { task?: string; status?: string };
  if (!task) return;
  ctx.thinking.subKaniTaskEnd(task, status);
}
