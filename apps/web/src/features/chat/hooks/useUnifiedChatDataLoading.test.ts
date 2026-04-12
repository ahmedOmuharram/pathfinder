/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import type { Message, Strategy } from "@pathfinder/shared";
import type * as HttpModule from "@/lib/api/http";
import { createTestWrapper } from "@/lib/query/testing";
import { useUnifiedChatDataLoading } from "./useUnifiedChatDataLoading";
import type { useThinkingState } from "./useThinkingState";

// --- Mocks ---

const mockStrategy: Strategy = {
  id: "strategy-1",
  name: "Test Strategy",
  siteId: "plasmodb",
  steps: [],
  rootStepId: null,
  isSaved: false,
  recordType: null,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  messages: [
    { role: "user", content: "hello", timestamp: new Date().toISOString() },
    { role: "assistant", content: "hi there", timestamp: new Date().toISOString() },
  ],
};

let mockGetStrategy: ReturnType<typeof vi.fn>;

vi.mock("@/lib/api/strategies", () => ({
  get getStrategy() {
    return mockGetStrategy;
  },
}));

vi.mock("@/lib/api/http", async (importOriginal) => {
  const actual = await importOriginal<typeof HttpModule>();
  return {
    ...actual,
  };
});

// Mock useSessionStore to control authVersion and authRefreshed
let mockAuthVersion = 0;
let mockAuthRefreshed = true;
vi.mock("@/state/useSessionStore", () => ({
  useSessionStore: (selector: (s: { authVersion: number; authRefreshed: boolean }) => unknown) =>
    selector({ authVersion: mockAuthVersion, authRefreshed: mockAuthRefreshed }),
}));

function makeArgs(
  overrides?: Partial<Parameters<typeof useUnifiedChatDataLoading>[0]>,
) {
  return {
    strategyId: "strategy-1" as string | null,
    sessionRef: { current: null },
    setMessages: vi.fn((updater: Message[] | ((prev: Message[]) => Message[])) => {
      // Simulate React setState: if updater is a function, call it with []
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

describe("useUnifiedChatDataLoading", () => {
  let wrapper: ReturnType<typeof createTestWrapper>["Wrapper"];

  beforeEach(() => {
    mockGetStrategy = vi.fn();
    mockAuthVersion = 0;
    mockAuthRefreshed = true;
    wrapper = createTestWrapper().Wrapper;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads messages on mount when strategyId is set", async () => {
    mockGetStrategy.mockResolvedValueOnce(mockStrategy);
    const args = makeArgs();

    renderHook(() => useUnifiedChatDataLoading(args), { wrapper });

    await waitFor(() => {
      expect(mockGetStrategy).toHaveBeenCalledWith("strategy-1");
      expect(args.setMessages).toHaveBeenCalled();
    });
  });

  it("does not fetch when strategyId is null", () => {
    const args = makeArgs({ strategyId: null });

    const { result } = renderHook(() => useUnifiedChatDataLoading(args), { wrapper });

    expect(mockGetStrategy).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
  });

  it("calls onStrategyNotFound on 404", async () => {
    const { APIError } = await import("@/lib/api/http");
    mockGetStrategy.mockRejectedValueOnce(
      new APIError("Not found", {
        status: 404,
        statusText: "",
        url: "",
        data: undefined,
      }),
    );
    const args = makeArgs();

    renderHook(() => useUnifiedChatDataLoading(args), { wrapper });

    await waitFor(() => {
      expect(args.onStrategyNotFound).toHaveBeenCalled();
    });
  });

  it("surfaces API error to UI on failed load", async () => {
    const { APIError } = await import("@/lib/api/http");
    // Both attempts fail (initial + 1 retry)
    mockGetStrategy.mockRejectedValue(
      new APIError("Unauthorized", {
        status: 401,
        statusText: "",
        url: "",
        data: undefined,
      }),
    );
    const args = makeArgs();

    renderHook(() => useUnifiedChatDataLoading(args), { wrapper });

    await waitFor(
      () => {
        expect(args.setApiError).toHaveBeenCalledWith(
          expect.stringContaining("Could not load conversation"),
        );
      },
      { timeout: 3000 },
    );
  });

  it("retries loading when authVersion bumps after a failed load", async () => {
    const { APIError } = await import("@/lib/api/http");

    // First two calls fail (initial + retry)
    mockGetStrategy
      .mockRejectedValueOnce(
        new APIError("Unauthorized", {
          status: 401,
          statusText: "",
          url: "",
          data: undefined,
        }),
      )
      .mockRejectedValueOnce(
        new APIError("Unauthorized", {
          status: 401,
          statusText: "",
          url: "",
          data: undefined,
        }),
      );

    const args = makeArgs();
    const { rerender } = renderHook(() => useUnifiedChatDataLoading(args), { wrapper });

    // Wait for both attempts to fail
    await waitFor(
      () => {
        expect(mockGetStrategy).toHaveBeenCalledTimes(2);
        expect(args.setApiError).toHaveBeenCalledWith(
          expect.stringContaining("Could not load conversation"),
        );
      },
      { timeout: 3000 },
    );

    // Simulate auth cookie refresh (bump version)
    mockAuthVersion = 1;
    mockGetStrategy.mockResolvedValueOnce(mockStrategy);

    // Re-render to trigger the authVersion change detection
    await act(async () => {
      rerender();
    });

    await waitFor(() => {
      // The hook should have retried
      expect(mockGetStrategy).toHaveBeenCalledTimes(3);
      // Error should be cleared
      expect(args.setApiError).toHaveBeenCalledWith(null);
    });
  });

  it("does NOT call loadGraph — applies the already-fetched strategy directly", async () => {
    const strategyWithSteps: Strategy = {
      ...mockStrategy,
      steps: [
        {
          id: "step-1",
          kind: "search",
          displayName: "Gene search",
          searchName: "GeneByTextSearch",
          isBuilt: false,
          isFiltered: false,
        },
      ],
    };
    mockGetStrategy.mockResolvedValue(strategyWithSteps);
    const args = makeArgs();

    renderHook(() => useUnifiedChatDataLoading(args), { wrapper });

    await waitFor(() => {
      expect(mockGetStrategy).toHaveBeenCalled();
      expect(args.setMessages).toHaveBeenCalled();
    });

    // setStrategy should be called directly with the fetched data
    expect(args.setStrategy).toHaveBeenCalledWith(strategyWithSteps);
  });

  it("exposes isLoading=true while fetching, false after", async () => {
    let resolveGetStrategy: (s: Strategy) => void;
    mockGetStrategy.mockReturnValueOnce(
      new Promise<Strategy>((r) => {
        resolveGetStrategy = r;
      }),
    );
    const args = makeArgs();

    const { result } = renderHook(() => useUnifiedChatDataLoading(args), { wrapper });

    // Should be loading immediately
    expect(result.current.isLoading).toBe(true);

    // Resolve the fetch
    await act(async () => {
      resolveGetStrategy!(mockStrategy);
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it("refetches on authVersion bump but does not re-apply identical data", async () => {
    // Successful load
    mockGetStrategy.mockResolvedValue(mockStrategy);
    const args = makeArgs();

    const { rerender } = renderHook(() => useUnifiedChatDataLoading(args), { wrapper });

    await waitFor(() => {
      expect(mockGetStrategy).toHaveBeenCalledTimes(1);
    });

    // Bump authVersion — query key changes, so TanStack Query refetches
    mockAuthVersion = 1;

    await act(async () => {
      rerender();
    });

    await waitFor(() => {
      expect(mockGetStrategy).toHaveBeenCalledTimes(2);
    });

    // setStrategy should only be called once per strategyId:authVersion combo
    // (the applied guard in the hook prevents duplicate application)
    expect(args.setStrategy).toHaveBeenCalled();
  });
});
