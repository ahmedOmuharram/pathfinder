/**
 * Regression tests for useUnifiedChatDataLoading — Race D.
 *
 * Race D: When a strategy REST response arrives while a stream is still
 * in-flight, the hook merges the fetched messages via
 * `setMessages((prev) => mergeMessages(prev, incoming))`. The heuristic
 * used by `mergeMessages` is length-based: it returns `incoming` if
 * `incoming.length >= prev.length`. During streaming, `prev` holds the
 * user's just-appended message + a partial assistant delta; the REST
 * response holds an older snapshot with equal or greater length. If the
 * REST snapshot is stale (older assistant content) but length-equal, it
 * can overwrite the in-flight streaming content.
 *
 * Expected post-fix behavior:
 *   - In-flight streaming content is preserved: a REST response arriving
 *     during streaming MUST NOT replace a streaming message with a
 *     stale version.
 *
 * @vitest-environment jsdom
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import type { Message, Strategy } from "@pathfinder/shared";
import { createTestWrapper } from "@/lib/query/testing";
import { useUnifiedChatDataLoading } from "./useUnifiedChatDataLoading";
import { mergeMessages } from "@/features/chat/utils/mergeMessages";
import type { useThinkingState } from "./useThinkingState";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockGetStrategy: ReturnType<typeof vi.fn>;

vi.mock("@/lib/api/strategies", () => ({
  get getStrategy() {
    return mockGetStrategy;
  },
}));

let mockAuthVersion = 0;
const mockAuthRefreshed = true;
vi.mock("@/state/useSessionStore", () => {
  const store = (
    selector: (s: { authVersion: number; authRefreshed: boolean }) => unknown,
  ) => selector({ authVersion: mockAuthVersion, authRefreshed: mockAuthRefreshed });
  // usePlanStore attaches a subscribe listener at module load time.
  Object.assign(store, {
    subscribe: vi.fn(() => () => undefined),
    getState: vi.fn(() => ({
      authVersion: mockAuthVersion,
      authRefreshed: mockAuthRefreshed,
      strategyId: null,
    })),
  });
  return { useSessionStore: store };
});

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeUserMessage(content: string, ts = "2026-04-10T00:00:00Z"): Message {
  return { role: "user", content, timestamp: ts };
}

function makeAssistantMessage(content: string, ts = "2026-04-10T00:00:01Z"): Message {
  return { role: "assistant", content, timestamp: ts };
}

function makeArgs(
  overrides?: Partial<Parameters<typeof useUnifiedChatDataLoading>[0]>,
) {
  return {
    strategyId: "strategy-1" as string | null,
    sessionRef: { current: null },
    setMessages: vi.fn(),
    setApiError: vi.fn(),
    setSelectedModelId: vi.fn(),
    thinking: {
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
      applyThinkingPayload: vi.fn(() => false),
      reset: vi.fn(),
      updateActiveFromBuffer: vi.fn(),
      updateReasoning: vi.fn(),
      finalizeToolCalls: vi.fn(),
    } as unknown as ReturnType<typeof useThinkingState>,
    setStrategy: vi.fn(),
    setStrategyMeta: vi.fn(),
    onStrategyNotFound: vi.fn(),
    ...overrides,
  };
}

function makeStrategy(messages: Message[]): Strategy {
  return {
    id: "strategy-1",
    name: "Test Strategy",
    siteId: "plasmodb",
    steps: [],
    rootStepId: null,
    isSaved: false,
    recordType: null,
    createdAt: "2026-04-10T00:00:00Z",
    updatedAt: "2026-04-10T00:00:00Z",
    messages,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useUnifiedChatDataLoading — Race D (REST overwrites streaming)", () => {
  let wrapper: ReturnType<typeof createTestWrapper>["Wrapper"];

  beforeEach(() => {
    mockGetStrategy = vi.fn();
    mockAuthVersion = 0;
    wrapper = createTestWrapper().Wrapper;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("REST response does not replace an in-flight streaming assistant message with a stale one", async () => {
    // Simulate: streaming has already produced a partial assistant message.
    const inflightUser = makeUserMessage("ask me anything");
    const inflightAssistant = makeAssistantMessage(
      "PARTIAL streaming response (in-flight)",
    );
    const inflight: Message[] = [inflightUser, inflightAssistant];

    // REST server returns a stale snapshot of the SAME length: the
    // assistant content is older. If the hook naively merges, the stale
    // content overwrites the fresh in-flight content.
    const staleAssistant = makeAssistantMessage(
      "OLD stale response",
      "2026-04-10T00:00:00.500Z",
    );
    const restSnapshot: Message[] = [
      makeUserMessage("ask me anything"),
      staleAssistant,
    ];

    // Capture the final message list that would be committed to state.
    let committed: Message[] | null = null;
    const setMessages = vi.fn(
      (updater: Message[] | ((prev: Message[]) => Message[])) => {
        committed =
          typeof updater === "function"
            ? (updater as (prev: Message[]) => Message[])(inflight)
            : updater;
      },
    );

    mockGetStrategy.mockResolvedValueOnce(makeStrategy(restSnapshot));

    const args = makeArgs({ setMessages });
    renderHook(() => useUnifiedChatDataLoading(args), { wrapper });

    await waitFor(() => {
      expect(mockGetStrategy).toHaveBeenCalled();
      expect(setMessages).toHaveBeenCalled();
    });

    // Post-fix expectation: committed list still carries the in-flight
    // streaming assistant content -- NOT the older REST version.
    expect(committed).not.toBeNull();
    const assistantMsgs = (committed as unknown as Message[]).filter(
      (m): m is Extract<Message, { role: "assistant" }> => m.role === "assistant",
    );
    expect(assistantMsgs).toHaveLength(1);
    expect(assistantMsgs[0]!.content).toBe("PARTIAL streaming response (in-flight)");
  });

  it("mergeMessages with equal-length arrays currently replaces content when it differs (documents Race D)", () => {
    // This test documents the weakness of the current mergeMessages heuristic.
    // Because incoming.length === current.length, `mergeMessages` walks
    // message-by-message; at each position, if the `content` differs between
    // `cur` and `msg`, the incoming `msg` wins. This is Race D in miniature.
    const current: Message[] = [
      makeUserMessage("hi"),
      makeAssistantMessage("FRESH streaming delta"),
    ];
    const incoming: Message[] = [
      makeUserMessage("hi"),
      makeAssistantMessage("OLD stale"),
    ];

    const merged = mergeMessages(current, incoming);

    // Document: the second assistant message content is overwritten by the
    // incoming (stale) value today. The post-fix behavior requires the
    // caller/merge strategy to detect and skip during in-flight streaming.
    const assistant = merged.find((m) => m.role === "assistant");
    expect(assistant).toBeDefined();
    // Post-fix expectation: assistant content stays as FRESH streaming delta.
    expect(assistant!.content).toBe("FRESH streaming delta");
  });

  it("REST response shorter than in-flight is dropped (sanity regression)", () => {
    // Pure mergeMessages semantics: when incoming is shorter, it must be
    // rejected. This is the one case mergeMessages gets right today.
    const current: Message[] = [
      makeUserMessage("hi"),
      makeAssistantMessage("FRESH streaming delta"),
    ];
    const incoming: Message[] = [makeUserMessage("hi")];

    const merged = mergeMessages(current, incoming);

    expect(merged).toEqual(current);
    // Assistant content is untouched.
    const assistant = merged.find((m) => m.role === "assistant");
    expect(assistant?.content).toBe("FRESH streaming delta");
  });
});
