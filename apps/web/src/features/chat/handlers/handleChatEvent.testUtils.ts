import { vi } from "vitest";
import type {
  Citation,
  Message,
  PlanningArtifact,
  Strategy,
  ToolCall,
} from "@pathfinder/shared";
import type { ChatEventContext } from "./handleChatEvent.types";
import { StreamingSession } from "@/features/chat/streaming/StreamingSession";

type SetStateAction<T> = T | ((prev: T) => T);
type UndoSnapshots = Record<number, Strategy>;

export function makeStateSetters() {
  let messages: Message[] = [];
  let undoSnapshots: UndoSnapshots = {};

  const setMessages = (updater: SetStateAction<Message[]>) => {
    messages = typeof updater === "function" ? updater(messages) : updater;
  };
  const setUndoSnapshots = (updater: SetStateAction<UndoSnapshots>) => {
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
  let undoSnapshots: UndoSnapshots = {};
  const messageQueue: ((prev: Message[]) => Message[])[] = [];
  const snapshotQueue: ((prev: UndoSnapshots) => UndoSnapshots)[] = [];

  const setMessages = (updater: SetStateAction<Message[]>) => {
    if (typeof updater === "function") messageQueue.push(updater);
    else messages = updater;
  };
  const setUndoSnapshots = (updater: SetStateAction<UndoSnapshots>) => {
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

export function makeCtx(overrides?: Partial<ChatEventContext>) {
  const toolCallsBuffer: ToolCall[] = [];
  const citationsBuffer: Citation[] = [];
  const planningArtifactsBuffer: PlanningArtifact[] = [];
  const subKaniCallsBuffer: Record<string, ToolCall[]> = {};
  const subKaniStatusBuffer: Record<string, string> = {};
  const state = makeStateSetters();
  const applyGraphSnapshot = vi.fn();
  const thinking: ChatEventContext["thinking"] = {
    activeToolCalls: [],
    lastToolCalls: [],
    subKaniCalls: {},
    subKaniStatus: {},
    reasoning: null,
    subKaniActivity: undefined,
    reset: vi.fn(),
    applyThinkingPayload: vi.fn(() => false),
    updateActiveFromBuffer: vi.fn(),
    finalizeToolCalls: vi.fn(),
    updateReasoning: vi.fn(),
    snapshotSubKaniActivity: vi.fn(() => ({ calls: {}, status: {} })),
    subKaniTaskStart: vi.fn(),
    subKaniToolCallStart: vi.fn(),
    subKaniToolCallEnd: vi.fn(),
    subKaniTaskEnd: vi.fn(),
  };

  const base = {
    siteId: "veupathdb",
    strategyIdAtStart: "s1",
    toolCallsBuffer,
    citationsBuffer,
    planningArtifactsBuffer,
    subKaniCallsBuffer,
    subKaniStatusBuffer,
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
    parseToolResult: vi.fn(() => ({ graphSnapshot: { graphId: "g1", steps: [] } })),
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
    setSelectedModelId: vi.fn(),
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
