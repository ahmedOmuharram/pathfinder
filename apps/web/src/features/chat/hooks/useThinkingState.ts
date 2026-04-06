import { useCallback, useState } from "react";
import type { ToolCall } from "@pathfinder/shared";

type ThinkingPayload = {
  toolCalls?: ToolCall[] | null;
  lastToolCalls?: ToolCall[] | null;
  reasoning?: string | null;
  updatedAt?: string | null;
};

export function useThinkingState() {
  const [activeToolCalls, setActiveToolCalls] = useState<ToolCall[]>([]);
  const [lastToolCalls, setLastToolCalls] = useState<ToolCall[]>([]);
  const [reasoning, setReasoning] = useState<string | null>(null);

  const reset = useCallback(() => {
    setActiveToolCalls([]);
    setLastToolCalls([]);
    setReasoning(null);
  }, []);

  const applyThinkingPayload = useCallback(
    (payload: ThinkingPayload | null): boolean => {
      if (payload == null) return false;
      const updatedAt =
        payload.updatedAt != null && payload.updatedAt !== ""
          ? new Date(payload.updatedAt).getTime()
          : 0;
      const isStale = updatedAt === 0 || Date.now() - updatedAt > 10 * 60 * 1000;
      if (isStale) return false;
      const toolCalls = payload.toolCalls ?? [];
      setActiveToolCalls(toolCalls);
      setLastToolCalls(payload.lastToolCalls ?? []);
      setReasoning(typeof payload.reasoning === "string" ? payload.reasoning : null);

      const anyActiveTool = toolCalls.some(
        (c) => c != null && (c.result === undefined || c.result === null),
      );
      return anyActiveTool;
    },
    [],
  );

  const updateReasoning = useCallback((text: string | null) => {
    setReasoning(text);
  }, []);

  const updateActiveFromBuffer = useCallback((toolCalls: ToolCall[]) => {
    setActiveToolCalls(toolCalls);
  }, []);

  const finalizeToolCalls = useCallback((toolCalls: ToolCall[]) => {
    setLastToolCalls(toolCalls);
    setActiveToolCalls([]);
  }, []);

  return {
    activeToolCalls,
    lastToolCalls,
    reasoning,
    reset,
    applyThinkingPayload,
    updateActiveFromBuffer,
    finalizeToolCalls,
    updateReasoning,
  };
}
