import { vi } from "vitest";
import type {
  ToolCall,
  Citation,
  PlanningArtifact,
  Strategy,
  Message,
  SubKaniTokenUsage,
} from "@pathfinder/shared";
import { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import type { ChatEventContext, StreamSessionState } from "../handleChatEvent.types";

/**
 * Creates a properly-typed mock `ChatEventContext` for handler tests.
 *
 * All action functions are `vi.fn()` mocks. Override any field by passing
 * a partial object.
 */
export function createMockChatContext(
  overrides: Partial<ChatEventContext> = {},
): ChatEventContext {
  const toolCallsBuffer: ToolCall[] = [];
  const citationsBuffer: Citation[] = [];
  const planningArtifactsBuffer: PlanningArtifact[] = [];
  const subKaniCallsBuffer: Record<string, ToolCall[]> = {};
  const subKaniStatusBuffer: Record<string, string> = {};
  const subKaniModelsBuffer: Record<string, string> = {};
  const subKaniTokenUsageBuffer: Record<string, SubKaniTokenUsage> = {};

  const streamState: StreamSessionState = {
    streamingAssistantIndex: null,
    streamingAssistantMessageId: null,
    turnAssistantIndex: null,
    reasoning: null,
    optimizationProgress: null,
  };

  const messages: Message[] = [];

  return {
    siteId: "plasmodb",
    strategyIdAtStart: "s1",
    toolCallsBuffer,
    citationsBuffer,
    planningArtifactsBuffer,
    subKaniCallsBuffer,
    subKaniStatusBuffer,
    subKaniModelsBuffer,
    subKaniTokenUsageBuffer,
    thinking: {
      activeToolCalls: [],
      lastToolCalls: [],
      subKaniCalls: {},
      subKaniStatus: {},
      subKaniModels: {},
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
    },
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
    setMessages: vi.fn((updater) => {
      if (typeof updater === "function") {
        const next = updater(messages);
        messages.length = 0;
        messages.push(...next);
      }
    }),
    setUndoSnapshots: vi.fn(),
    parseToolArguments: vi.fn(() => ({})),
    parseToolResult: vi.fn(() => null),
    applyGraphSnapshot: vi.fn(),
    getStrategy: vi.fn(async () => null as unknown as Strategy),
    streamState,
    setOptimizationProgress: vi.fn(),
    setSelectedModelId: vi.fn(),
    ...overrides,
  };
}
