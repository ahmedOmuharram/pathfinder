import { vi } from "vitest";
import type {
  Citation,
  Message,
  PlanningArtifact,
  ProblemFrame,
  Strategy,
  ToolCall,
} from "@pathfinder/shared";
import type { ChatEventContext } from "./handleChatEvent.types";
import { StreamingSession } from "@/features/chat/streaming/StreamingSession";

type SetStateAction<T> = T | ((prev: T) => T);
type UndoSnapshots = Record<number, Strategy>;

function makeStateSetters() {
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
  let problemFrameBuffer: ProblemFrame | null = null;
  const state = makeStateSetters();
  const applyGraphSnapshot = vi.fn();
  const thinking: ChatEventContext["thinking"] = {
    activeMessageId: null,
    activeToolCalls: [],
    lastToolCalls: [],
    reasoning: null,
    getThinkingForMessage: vi.fn(() => ({
      activeToolCalls: [],
      lastToolCalls: [],
      reasoning: null,
    })),
    setActiveMessage: vi.fn(),
    reset: vi.fn(),
    applyThinkingPayload: vi.fn(() => false),
    updateActiveFromBuffer: vi.fn(),
    finalizeToolCalls: vi.fn(),
    updateReasoning: vi.fn(),
  };

  const base = {
    siteId: "veupathdb",
    strategyIdAtStart: "s1",
    toolCallsBuffer,
    citationsBuffer,
    planningArtifactsBuffer,
    get problemFrameBuffer() {
      return problemFrameBuffer;
    },
    set problemFrameBuffer(value) {
      problemFrameBuffer = value;
    },
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
    session: new StreamingSession(),
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
      assistantMessageIndices: {},
      turnAssistantIndex: null,
      lastAssistantMessageId: null,
      messageGroupId: null,
      currentPhase: null,
      pipeline: null,
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
