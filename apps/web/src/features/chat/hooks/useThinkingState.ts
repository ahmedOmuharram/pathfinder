import { useRef, useState } from "react";
import type { ToolCall } from "@pathfinder/shared";

type ThinkingPayload = {
  toolCalls?: ToolCall[] | null;
  lastToolCalls?: ToolCall[] | null;
  reasoning?: string | null;
  updatedAt?: string | null;
};

export type ThinkingSnapshot = {
  activeToolCalls: ToolCall[];
  lastToolCalls: ToolCall[];
  reasoning: string | null;
};

const FALLBACK_THINKING_KEY = "__default__";

const EMPTY_SNAPSHOT: ThinkingSnapshot = {
  activeToolCalls: [],
  lastToolCalls: [],
  reasoning: null,
};

function resolveThinkingKey(messageId: string | null | undefined): string {
  return messageId != null && messageId !== ""
    ? messageId
    : FALLBACK_THINKING_KEY;
}

export function useThinkingState() {
  const [thinkingByMessageId, setThinkingByMessageId] = useState<
    Record<string, ThinkingSnapshot>
  >({});
  const [activeMessageId, setActiveMessageIdState] = useState<string | null>(null);
  const activeMessageIdRef = useRef<string | null>(null);

  const getThinkingForMessage = (messageId?: string | null): ThinkingSnapshot => {
    const key = resolveThinkingKey(messageId ?? activeMessageId);
    return thinkingByMessageId[key] ?? EMPTY_SNAPSHOT;
  };

  const updateThinkingForMessage = (
    messageId: string | null | undefined,
    updater: (current: ThinkingSnapshot) => ThinkingSnapshot,
  ) => {
    const key = resolveThinkingKey(messageId);
    setThinkingByMessageId((prev) => {
      const current = prev[key] ?? EMPTY_SNAPSHOT;
      return {
        ...prev,
        [key]: updater(current),
      };
    });
  };

  const setActiveMessage = (messageId: string | null) => {
    const normalized = messageId != null && messageId !== "" ? messageId : null;
    activeMessageIdRef.current = normalized;
    setActiveMessageIdState(normalized);
  };

  const reset = () => {
    activeMessageIdRef.current = null;
    setActiveMessageIdState(null);
    setThinkingByMessageId({});
  };

  const applyThinkingPayload = (payload: ThinkingPayload | null): boolean => {
    if (payload == null) return false;
    const updatedAt =
      payload.updatedAt != null && payload.updatedAt !== ""
        ? new Date(payload.updatedAt).getTime()
        : 0;
    const isStale = updatedAt === 0 || Date.now() - updatedAt > 10 * 60 * 1000;
    if (isStale) return false;
    const toolCalls = payload.toolCalls ?? [];
    activeMessageIdRef.current = null;
    setActiveMessageIdState(null);
    setThinkingByMessageId({
      [FALLBACK_THINKING_KEY]: {
        activeToolCalls: toolCalls,
        lastToolCalls: payload.lastToolCalls ?? [],
        reasoning: typeof payload.reasoning === "string" ? payload.reasoning : null,
      },
    });

    const anyActiveTool = toolCalls.some(
      (c) => c.result === undefined || c.result === null,
    );
    return anyActiveTool;
  };

  const updateReasoning = (text: string | null, messageId?: string | null) => {
    updateThinkingForMessage(messageId ?? activeMessageIdRef.current, (current) => ({
      ...current,
      reasoning: text,
    }));
  };

  const updateActiveFromBuffer = (
    toolCalls: ToolCall[],
    messageId?: string | null,
  ) => {
    updateThinkingForMessage(messageId ?? activeMessageIdRef.current, (current) => ({
      ...current,
      activeToolCalls: toolCalls,
    }));
  };

  const finalizeToolCalls = (toolCalls: ToolCall[], messageId?: string | null) => {
    updateThinkingForMessage(messageId ?? activeMessageIdRef.current, (current) => ({
      ...current,
      lastToolCalls: toolCalls,
      activeToolCalls: [],
    }));
  };

  const activeThinking = getThinkingForMessage(activeMessageId);

  return {
    activeMessageId,
    activeToolCalls: activeThinking.activeToolCalls,
    lastToolCalls: activeThinking.lastToolCalls,
    reasoning: activeThinking.reasoning,
    getThinkingForMessage,
    setActiveMessage,
    reset,
    applyThinkingPayload,
    updateActiveFromBuffer,
    finalizeToolCalls,
    updateReasoning,
  };
}
