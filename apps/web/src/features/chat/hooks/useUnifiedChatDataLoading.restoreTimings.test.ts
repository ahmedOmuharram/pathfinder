/**
 * Regression tests for Issue 5, Part C: on page reload, the REST strategy
 * response carries a ``conversationState.phaseTimings`` map, and
 * ``useUnifiedChatDataLoading`` must replay each entry into
 * ``usePlanStore`` via ``setPhase(phase, status, timing)`` so that elapsed-time
 * labels and phase history reappear without waiting for a fresh SSE stream.
 *
 * These tests currently FAIL because the hook only forwards the current
 * phase/status and drops every timing field.
 *
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import type { Message, Strategy } from "@pathfinder/shared";
import { createTestWrapper } from "@/lib/query/testing";
import { usePlanStore } from "@/state/usePlanStore";
import { useUnifiedChatDataLoading } from "./useUnifiedChatDataLoading";
import type { useThinkingState } from "./useThinkingState";

let mockGetStrategy: ReturnType<typeof vi.fn>;

vi.mock("@/lib/api/strategies", () => ({
  get getStrategy() {
    return mockGetStrategy;
  },
}));

let mockAuthVersion = 0;
let mockAuthRefreshed = true;
vi.mock("@/state/useSessionStore", () => {
  // The real ``useSessionStore`` is a Zustand store with a ``.subscribe``
  // method; ``usePlanStore`` calls ``useSessionStore.subscribe`` at module load
  // to clear plan state when the strategy ID changes. The mock must expose
  // that method so the import graph doesn't blow up.
  const fn = ((selector: (s: { authVersion: number; authRefreshed: boolean }) => unknown) =>
    selector({ authVersion: mockAuthVersion, authRefreshed: mockAuthRefreshed })) as unknown as {
    (selector: (s: { authVersion: number; authRefreshed: boolean }) => unknown): unknown;
    subscribe: (
      ...args: Parameters<typeof Function.prototype.apply>
    ) => () => void;
    getState: () => { authVersion: number; authRefreshed: boolean };
  };
  fn.subscribe = () => () => {};
  fn.getState = () => ({
    authVersion: mockAuthVersion,
    authRefreshed: mockAuthRefreshed,
  });
  return { useSessionStore: fn };
});

function resetPlanStore(): void {
  usePlanStore.setState({
    activePlan: null,
    activePlanTraceId: null,
    activePlanMessageGroupId: null,
    isPlanPinned: false,
    planThoughts: [],
    sendMessage: null,
    submitPlanAction: null,
    currentPhase: null,
    phaseStatus: null,
    phaseTimings: {},
  });
}

function makeArgs(
  overrides?: Partial<Parameters<typeof useUnifiedChatDataLoading>[0]>,
) {
  return {
    strategyId: "strategy-1" as string | null,
    sessionRef: { current: null },
    setMessages: vi.fn((updater: Message[] | ((prev: Message[]) => Message[])) => {
      if (typeof updater === "function") updater([]);
    }),
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
      applyThinkingPayload: vi.fn(),
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

function makeStrategy(conversationState: Record<string, unknown>): Strategy {
  return {
    id: "strategy-1",
    name: "Test Strategy",
    siteId: "plasmodb",
    steps: [],
    rootStepId: null,
    isSaved: false,
    recordType: null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    messages: [],
    conversationState,
  } as Strategy;
}

describe("useUnifiedChatDataLoading — phase timing restoration", () => {
  let wrapper: ReturnType<typeof createTestWrapper>["Wrapper"];

  beforeEach(() => {
    mockGetStrategy = vi.fn();
    mockAuthVersion = 0;
    mockAuthRefreshed = true;
    wrapper = createTestWrapper().Wrapper;
    resetPlanStore();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    resetPlanStore();
  });

  it("restores phase timings from conversationState into usePlanStore", async () => {
    const strategy = makeStrategy({
      currentPhase: "execution",
      phaseStatus: "started",
      phaseTimings: {
        scoping: {
          phase: "scoping",
          status: "completed",
          emittedAt: "2026-04-12T10:00:45Z",
          phaseStartedAt: "2026-04-12T10:00:00Z",
          phaseCompletedAt: "2026-04-12T10:00:45Z",
          durationMs: 45_000,
        },
        discovery: {
          phase: "discovery",
          status: "completed",
          emittedAt: "2026-04-12T10:02:00Z",
          phaseStartedAt: "2026-04-12T10:00:45Z",
          phaseCompletedAt: "2026-04-12T10:02:00Z",
          durationMs: 75_000,
        },
        execution: {
          phase: "execution",
          status: "started",
          emittedAt: "2026-04-12T10:02:00Z",
          phaseStartedAt: "2026-04-12T10:02:00Z",
          phaseCompletedAt: null,
          durationMs: null,
        },
      },
    });
    mockGetStrategy.mockResolvedValueOnce(strategy);
    const setPhase = vi.spyOn(usePlanStore.getState(), "setPhase");

    renderHook(() => useUnifiedChatDataLoading(makeArgs()), { wrapper });

    await waitFor(() => {
      expect(setPhase).toHaveBeenCalled();
    });

    // The hook must have invoked setPhase for each restored phase, with the
    // exact timing metadata. Order is unspecified, so assert individual calls.
    expect(setPhase).toHaveBeenCalledWith("scoping", "completed", {
      emittedAt: "2026-04-12T10:00:45Z",
      phaseStartedAt: "2026-04-12T10:00:00Z",
      phaseCompletedAt: "2026-04-12T10:00:45Z",
      durationMs: 45_000,
    });
    expect(setPhase).toHaveBeenCalledWith("discovery", "completed", {
      emittedAt: "2026-04-12T10:02:00Z",
      phaseStartedAt: "2026-04-12T10:00:45Z",
      phaseCompletedAt: "2026-04-12T10:02:00Z",
      durationMs: 75_000,
    });
    expect(setPhase).toHaveBeenCalledWith("execution", "started", {
      emittedAt: "2026-04-12T10:02:00Z",
      phaseStartedAt: "2026-04-12T10:02:00Z",
      phaseCompletedAt: null,
      durationMs: null,
    });

    // And the store must reflect the restored values verbatim.
    const store = usePlanStore.getState();
    expect(store.currentPhase).toBe("execution");
    expect(store.phaseStatus).toBe("started");
    const scoping = store.phaseTimings.scoping;
    expect(scoping?.durationMs).toBe(45_000);
    expect(scoping?.phaseStartedAt).toBe("2026-04-12T10:00:00Z");
    expect(scoping?.phaseCompletedAt).toBe("2026-04-12T10:00:45Z");
    const discovery = store.phaseTimings.discovery;
    expect(discovery?.durationMs).toBe(75_000);
    const execution = store.phaseTimings.execution;
    expect(execution?.phaseStartedAt).toBe("2026-04-12T10:02:00Z");
    expect(execution?.durationMs).toBeNull();
  });

  it("skips phaseTimings entries whose phase name is not a known pipeline phase", async () => {
    const strategy = makeStrategy({
      currentPhase: "scoping",
      phaseStatus: "started",
      phaseTimings: {
        scoping: {
          phase: "scoping",
          status: "started",
          emittedAt: "2026-04-12T10:00:00Z",
          phaseStartedAt: "2026-04-12T10:00:00Z",
          phaseCompletedAt: null,
          durationMs: null,
        },
        bogus_phase: {
          phase: "bogus_phase",
          status: "started",
          emittedAt: "2026-04-12T10:00:00Z",
          phaseStartedAt: "2026-04-12T10:00:00Z",
          phaseCompletedAt: null,
          durationMs: null,
        },
      },
    });
    mockGetStrategy.mockResolvedValueOnce(strategy);
    const setPhase = vi.spyOn(usePlanStore.getState(), "setPhase");

    renderHook(() => useUnifiedChatDataLoading(makeArgs()), { wrapper });

    await waitFor(() => {
      expect(setPhase).toHaveBeenCalledWith(
        "scoping",
        "started",
        expect.objectContaining({ phaseStartedAt: "2026-04-12T10:00:00Z" }),
      );
    });

    // The unknown phase name must never reach the store.
    const unknownCalls = setPhase.mock.calls.filter(
      (call) => call[0] === ("bogus_phase" as unknown),
    );
    expect(unknownCalls).toHaveLength(0);
    expect(
      (usePlanStore.getState().phaseTimings as Record<string, unknown>)[
        "bogus_phase"
      ],
    ).toBeUndefined();
  });

  it("handles strategies whose conversationState omits phaseTimings", async () => {
    const strategy = makeStrategy({
      currentPhase: "scoping",
      phaseStatus: "started",
      // No phaseTimings key at all — hook must still restore the current phase.
    });
    mockGetStrategy.mockResolvedValueOnce(strategy);
    const setPhase = vi.spyOn(usePlanStore.getState(), "setPhase");

    renderHook(() => useUnifiedChatDataLoading(makeArgs()), { wrapper });

    await waitFor(() => {
      expect(setPhase).toHaveBeenCalled();
    });

    // When phaseTimings is absent, the hook must not invent timing entries
    // with fabricated dates. Only the current-phase setPhase call is allowed,
    // with no timing argument.
    expect(setPhase).toHaveBeenCalledWith("scoping", "started");
    const timedCalls = setPhase.mock.calls.filter((call) => call.length >= 3);
    expect(timedCalls).toHaveLength(0);

    // The store has recorded the current phase itself...
    expect(usePlanStore.getState().currentPhase).toBe("scoping");
    // ...without a parallel phaseTimings payload, because REST didn't send one.
    const scopingTiming = usePlanStore.getState().phaseTimings.scoping;
    expect(
      scopingTiming === undefined
        || (scopingTiming.phaseStartedAt === null
          && scopingTiming.phaseCompletedAt === null
          && scopingTiming.durationMs === null
          && scopingTiming.emittedAt === null),
    ).toBe(true);
  });
});
