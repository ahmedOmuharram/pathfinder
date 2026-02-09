import type { Citation, Message, PlanningArtifact, ToolCall } from "@pathfinder/shared";

export type StreamingAssistantState = {
  index: number | null;
  messageId: string | null;
};

export function applyAssistantDelta(args: {
  messages: Message[];
  streaming: StreamingAssistantState;
  event: { messageId?: string; delta?: string };
  nowIso: () => string;
}): { messages: Message[]; streaming: StreamingAssistantState } {
  const { messages, streaming, event, nowIso } = args;
  const { messageId, delta } = event;
  if (!delta) return { messages, streaming };

  // Start a new streaming assistant message when none exists (or message id changed).
  if (streaming.index === null || (messageId && streaming.messageId !== messageId)) {
    const assistantMessage: Message = {
      role: "assistant",
      content: delta,
      timestamp: nowIso(),
    };
    const next = [...messages, assistantMessage];
    return {
      messages: next,
      streaming: { index: next.length - 1, messageId: messageId || null },
    };
  }

  const idx = streaming.index;
  if (idx === null || idx < 0 || idx >= messages.length) return { messages, streaming };
  const existing = messages[idx];
  if (!existing || existing.role !== "assistant") return { messages, streaming };

  const next = [...messages];
  next[idx] = { ...existing, content: (existing.content || "") + delta };
  return { messages: next, streaming };
}

export function finalizeAssistantMessage(args: {
  messages: Message[];
  streaming: StreamingAssistantState;
  event: { messageId?: string; content?: string };
  toolCallsBuffer: ToolCall[];
  citationsBuffer: Citation[];
  artifactsBuffer: PlanningArtifact[];
  nowIso: () => string;
}): { messages: Message[]; streaming: StreamingAssistantState } {
  const {
    messages,
    streaming,
    event,
    toolCallsBuffer,
    citationsBuffer,
    artifactsBuffer,
    nowIso,
  } = args;

  const { messageId, content } = event;
  const finalContent = content || "";
  const idx = streaming.index;

  // Finalize an existing streaming message when ids match (or final messageId is absent).
  if (
    idx !== null &&
    idx >= 0 &&
    idx < messages.length &&
    (!messageId || streaming.messageId === messageId)
  ) {
    const existing = messages[idx];
    if (!existing || existing.role !== "assistant") {
      return { messages, streaming: { index: null, messageId: null } };
    }
    const next = [...messages];
    next[idx] = {
      ...existing,
      content: finalContent || existing.content,
      toolCalls: toolCallsBuffer.length > 0 ? [...toolCallsBuffer] : existing.toolCalls,
      citations: citationsBuffer.length > 0 ? [...citationsBuffer] : existing.citations,
      planningArtifacts:
        artifactsBuffer.length > 0 ? [...artifactsBuffer] : existing.planningArtifacts,
    };
    return { messages: next, streaming: { index: null, messageId: null } };
  }

  // Otherwise, append a standalone assistant message if content is present.
  if (finalContent) {
    const assistantMessage: Message = {
      role: "assistant",
      content: finalContent,
      toolCalls: toolCallsBuffer.length > 0 ? [...toolCallsBuffer] : undefined,
      citations: citationsBuffer.length > 0 ? [...citationsBuffer] : undefined,
      planningArtifacts: artifactsBuffer.length > 0 ? [...artifactsBuffer] : undefined,
      timestamp: nowIso(),
    };
    return {
      messages: [...messages, assistantMessage],
      streaming: { index: null, messageId: null },
    };
  }

  return { messages, streaming: { index: null, messageId: null } };
}

export function upsertSessionArtifact(
  prev: PlanningArtifact[],
  planningArtifact: PlanningArtifact,
): PlanningArtifact[] {
  const next = [...prev];
  const id = planningArtifact?.id;
  if (typeof id === "string" && id) {
    const idx = next.findIndex((a) => a.id === id);
    if (idx >= 0) next[idx] = planningArtifact;
    else next.push(planningArtifact);
    return next;
  }
  next.push(planningArtifact);
  return next;
}
