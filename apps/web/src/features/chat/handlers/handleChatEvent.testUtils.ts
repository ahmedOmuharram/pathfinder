/* eslint-disable @typescript-eslint/no-explicit-any */
import { vi } from "vitest";
import type { Message, ToolCall } from "@pathfinder/shared";
import { StreamingSession } from "@/features/chat/streaming/StreamingSession";

export function makeStateSetters() {
  let messages: Message[] = [];
  let undoSnapshots: Record<number, any> = {};

  const setMessages = (updater: any) => {
    messages = typeof updater === "function" ? updater(messages) : updater;
  };
  const setUndoSnapshots = (updater: any) => {
    undoSnapshots = typeof updater === "function" ? updater(undoSnapshots) : updater;
  };
  return {
    get messages() {
      return messages;
    },
    get undoSnapshots() {
      return undoSnapshots;
    },
    setMessages,
    setUndoSnapshots,
  };
}

/**
 * Simulates React 18 batching: updaters are queued and executed later
 * (as happens when multiple SSE events arrive in a single chunk).
 */
export function makeBatchingStateSetters() {
  let messages: Message[] = [];
  let undoSnapshots: Record<number, any> = {};
  const messageQueue: ((prev: Message[]) => Message[])[] = [];
  const snapshotQueue: ((prev: Record<number, any>) => Record<number, any>)[] = [];

  const setMessages = (updater: any) => {
    if (typeof updater === "function") messageQueue.push(updater);
    else messages = updater;
  };
  const setUndoSnapshots = (updater: any) => {
    if (typeof updater === "function") snapshotQueue.push(updater);
    else undoSnapshots = updater;
  };

  function flush() {
    for (const fn of messageQueue) messages = fn(messages);
    messageQueue.length = 0;
    for (const fn of snapshotQueue) undoSnapshots = fn(undoSnapshots);
    snapshotQueue.length = 0;
  }

  return {
    get messages() {
      return messages;
    },
    get undoSnapshots() {
      return undoSnapshots;
    },
    setMessages,
    setUndoSnapshots,
    flush,
  };
}

export function makeCtx(overrides?: Partial<any>) {
  const toolCallsBuffer: ToolCall[] = [];
  const citationsBuffer: any[] = [];
  const planningArtifactsBuffer: any[] = [];
  const state = makeStateSetters();
  const applyGraphSnapshot = vi.fn();
  const thinking = {
    updateActiveFromBuffer: vi.fn(),
    updateReasoning: vi.fn(),
    snapshotSubKaniActivity: vi.fn(() => ({ calls: {}, status: {} })),
    subKaniTaskStart: vi.fn(),
    subKaniToolCallStart: vi.fn(),
    subKaniToolCallEnd: vi.fn(),
    subKaniTaskEnd: vi.fn(),
  } as any;

  const base = {
    siteId: "plasmodb",
    strategyIdAtStart: "s1",
    toolCallsBuffer,
    citationsBuffer,
    planningArtifactsBuffer,
    thinking,
    setStrategyId: vi.fn(),
    addStrategy: vi.fn(),
    addExecutedStrategy: vi.fn(),
    setWdkInfo: vi.fn(),
    setStrategy: vi.fn(),
    setStrategyMeta: vi.fn(),
    clearStrategy: vi.fn(),
    addStep: vi.fn(),
    loadGraph: vi.fn(),
    session: new StreamingSession(null),
    currentStrategy: null,
    setMessages: state.setMessages,
    setUndoSnapshots: state.setUndoSnapshots,
    parseToolArguments: vi.fn(() => ({ a: 1 })),
    parseToolResult: vi.fn(() => ({ graphSnapshot: { x: 1 } })),
    applyGraphSnapshot,
    getStrategy: vi.fn(),
    streamState: {
      streamingAssistantIndex: null,
      streamingAssistantMessageId: null,
      turnAssistantIndex: null,
      reasoning: null,
      optimizationProgress: null,
    },
    setOptimizationProgress: vi.fn(),
  };

  const ctx = { ...base, ...(overrides ?? {}) };
  return {
    ctx,
    state,
    toolCallsBuffer,
    citationsBuffer,
    planningArtifactsBuffer,
    thinking,
    applyGraphSnapshot,
  };
}
