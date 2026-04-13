import type { AssistantMessage, Message, PlanningArtifact, ProblemFrame, OptimizationProgressData, ToolCall, Citation } from "@pathfinder/shared";
import type { StreamSessionState } from "./handleChatEvent.types";

/**
 * Resolve the current streaming assistant message index with fallback.
 *
 * If the tracked index is stale (null or negative), falls back to the
 * last message if it's an assistant message. Returns null when no valid
 * index can be resolved.
 */
export function resolveAssistantIndex(
  streamingIndex: number | null,
  messages: readonly Message[],
): number | null {
  let idx = streamingIndex;
  if (
    (idx === null || idx < 0) &&
    messages[messages.length - 1]?.role === "assistant"
  ) {
    idx = messages.length - 1;
  }
  if (idx === null || idx < 0 || idx >= messages.length) return null;
  return idx;
}

export function rememberAssistantIndex(
  streamState: StreamSessionState,
  messageId: string | null,
  index: number,
): void {
  if (messageId != null && messageId !== "") {
    streamState.assistantMessageIndices[messageId] = index;
    streamState.lastAssistantMessageId = messageId;
  }
  streamState.streamingAssistantIndex = index;
  streamState.turnAssistantIndex = index;
}

export function resolveAssistantIndexByMessageId(
  streamState: StreamSessionState,
  messages: readonly Message[],
  messageId: string | null,
): number | null {
  if (messageId != null && messageId !== "") {
    const remembered = streamState.assistantMessageIndices[messageId];
    if (remembered != null) {
      const msg = messages[remembered];
      if (msg?.role === "assistant" && msg.messageId === messageId) {
        return remembered;
      }
      delete streamState.assistantMessageIndices[messageId];
    }

    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const msg = messages[i];
      if (msg?.role !== "assistant") continue;
      if (msg.messageId !== messageId) continue;
      streamState.assistantMessageIndices[messageId] = i;
      return i;
    }

    return null;
  }

  return resolveAssistantIndex(streamState.streamingAssistantIndex, messages);
}

export function hasAssistantPayload(
  content: string,
  toolCalls?: ToolCall[],
  citations?: Citation[],
  artifacts?: PlanningArtifact[],
  problemFrame?: ProblemFrame | null,
  reasoning?: string,
  optimization?: OptimizationProgressData,
): boolean {
  if (content.trim() !== "") return true;
  if (toolCalls != null && toolCalls.length > 0) return true;
  if (citations != null && citations.length > 0) return true;
  if (artifacts != null && artifacts.length > 0) return true;
  if (problemFrame != null) return true;
  if (reasoning != null && reasoning.trim() !== "") return true;
  if (optimization != null) return true;
  return false;
}

export function buildAssistantIdentityFields(
  streamState: StreamSessionState,
  messageId: string | null,
): Partial<AssistantMessage> {
  const fields: Partial<AssistantMessage> = {};
  if (messageId != null && messageId !== "") {
    fields.messageId = messageId;
  }
  if (streamState.messageGroupId != null && streamState.messageGroupId !== "") {
    fields.messageGroupId = streamState.messageGroupId;
  }
  if (
    streamState.currentPhase === "discovery" ||
    streamState.currentPhase === "scoping" ||
    streamState.currentPhase === "planning" ||
    streamState.currentPhase === "execution" ||
    streamState.currentPhase === "verification"
  ) {
    fields.phase = streamState.currentPhase;
  }
  return fields;
}
