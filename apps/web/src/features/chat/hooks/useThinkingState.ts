import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ToolCall } from "@pathfinder/shared";

export type ThinkingPayload = {
  toolCalls?: ToolCall[];
  lastToolCalls?: ToolCall[];
  subKaniCalls?: Record<string, ToolCall[]>;
  subKaniStatus?: Record<string, string>;
  reasoning?: string;
  updatedAt?: string;
};

export function useThinkingState() {
  const [activeToolCalls, setActiveToolCalls] = useState<ToolCall[]>([]);
  const [lastToolCalls, setLastToolCalls] = useState<ToolCall[]>([]);
  const [subKaniCalls, setSubKaniCalls] = useState<Record<string, ToolCall[]>>({});
  const [subKaniStatus, setSubKaniStatus] = useState<Record<string, string>>({});
  const [reasoning, setReasoning] = useState<string | null>(null);

  const subKaniCallsRef = useRef<Record<string, ToolCall[]>>({});
  const subKaniStatusRef = useRef<Record<string, string>>({});

  useEffect(() => {
    subKaniCallsRef.current = subKaniCalls;
  }, [subKaniCalls]);

  useEffect(() => {
    subKaniStatusRef.current = subKaniStatus;
  }, [subKaniStatus]);

  const reset = useCallback(() => {
    setActiveToolCalls([]);
    setLastToolCalls([]);
    setSubKaniCalls({});
    setSubKaniStatus({});
    setReasoning(null);
  }, []);

  const applyThinkingPayload = useCallback((payload: ThinkingPayload | null): boolean => {
    if (!payload) return false;
    const updatedAt = payload.updatedAt ? new Date(payload.updatedAt).getTime() : 0;
    const isStale = !updatedAt || Date.now() - updatedAt > 10 * 60 * 1000;
    if (isStale) return false;
    const toolCalls = payload.toolCalls || [];
    setActiveToolCalls(toolCalls);
    setLastToolCalls(payload.lastToolCalls || []);
    setSubKaniCalls(payload.subKaniCalls || {});
    setSubKaniStatus(payload.subKaniStatus || {});
    setReasoning(typeof payload.reasoning === "string" ? payload.reasoning : null);

    const anyActiveTool = toolCalls.some(
      (c) => c && (c.result === undefined || c.result === null),
    );
    const anySubKaniRunning = Object.values(payload.subKaniStatus || {}).some(
      (s) => s === "running",
    );
    return anyActiveTool || anySubKaniRunning;
  }, []);

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

  const subKaniTaskStart = useCallback((task: string) => {
    setSubKaniStatus((prev) => ({ ...prev, [task]: "running" }));
    setSubKaniCalls((prev) => ({ ...prev, [task]: prev[task] || [] }));
  }, []);

  const subKaniToolCallStart = useCallback((task: string, toolCall: ToolCall) => {
    setSubKaniCalls((prev) => ({
      ...prev,
      [task]: [...(prev[task] || []), toolCall],
    }));
  }, []);

  const subKaniToolCallEnd = useCallback((task: string, id: string, result: string) => {
    setSubKaniCalls((prev) => {
      const calls = prev[task] || [];
      const updated = calls.map((call) => (call.id === id ? { ...call, result } : call));
      return { ...prev, [task]: updated };
    });
  }, []);

  const subKaniTaskEnd = useCallback((task: string, status?: string) => {
    setSubKaniStatus((prev) => ({ ...prev, [task]: status || "done" }));
  }, []);

  const subKaniActivity = useMemo(() => {
    const has = Object.keys(subKaniCalls).length > 0;
    if (!has) return undefined;
    return { calls: subKaniCalls, status: subKaniStatus };
  }, [subKaniCalls, subKaniStatus]);

  const snapshotSubKaniActivity = useCallback(() => {
    const calls = subKaniCallsRef.current;
    if (Object.keys(calls).length === 0) return undefined;
    return {
      calls: { ...calls },
      status: { ...subKaniStatusRef.current },
    };
  }, []);

  return {
    activeToolCalls,
    lastToolCalls,
    subKaniCalls,
    subKaniStatus,
    reasoning,
    subKaniActivity,
    reset,
    applyThinkingPayload,
    updateActiveFromBuffer,
    finalizeToolCalls,
    updateReasoning,
    subKaniTaskStart,
    subKaniToolCallStart,
    subKaniToolCallEnd,
    subKaniTaskEnd,
    snapshotSubKaniActivity,
  };
}

