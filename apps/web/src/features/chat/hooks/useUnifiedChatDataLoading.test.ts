/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import type { Message, Strategy } from "@pathfinder/shared";
import { useUnifiedChatDataLoading } from "./useUnifiedChatDataLoading";

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
  const actual = await importOriginal<typeof import("@/lib/api/http")>();
  return {
    ...actual,
  };
});

// Mock useSessionStore to control authVersion
let mockAuthVersion = 0;
vi.mock("@/state/useSessionStore", () => ({
  useSessionStore: (selector: (s: { authVersion: number }) => unknown) =>
    selector({ authVersion: mockAuthVersion }),
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
      applyThinkingPayload: vi.fn(),
      reset: vi.fn(),
      thinkingBudget: null,
      currentThinking: null,
      finalizeToolCalls: vi.fn(),
    } as unknown as ReturnType<typeof import("./useThinkingState").useThinkingState>,
    setStrategy: vi.fn(),
    setStrategyMeta: vi.fn(),
    onStrategyNotFound: vi.fn(),
    ...overrides,
  };
}

describe("useUnifiedChatDataLoading", () => {
  beforeEach(() => {
    mockGetStrategy = vi.fn();
    mockAuthVersion = 0;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads messages on mount when strategyId is set", async () => {
    mockGetStrategy.mockResolvedValueOnce(mockStrategy);
    const args = makeArgs();

    renderHook(() => useUnifiedChatDataLoading(args));

    await waitFor(() => {
      expect(mockGetStrategy).toHaveBeenCalledWith("strategy-1");
      expect(args.setMessages).toHaveBeenCalled();
    });
  });

  it("clears messages when strategyId is null", () => {
    const args = makeArgs({ strategyId: null });

    renderHook(() => useUnifiedChatDataLoading(args));

    expect(args.setMessages).toHaveBeenCalledWith([]);
    expect(mockGetStrategy).not.toHaveBeenCalled();
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

    renderHook(() => useUnifiedChatDataLoading(args));

    await waitFor(() => {
      expect(args.onStrategyNotFound).toHaveBeenCalled();
    });
  });

  it("surfaces API error to UI on failed load", async () => {
    const { APIError } = await import("@/lib/api/http");
    // Both attempts fail
    mockGetStrategy.mockRejectedValue(
      new APIError("Unauthorized", {
        status: 401,
        statusText: "",
        url: "",
        data: undefined,
      }),
    );
    const args = makeArgs();

    renderHook(() => useUnifiedChatDataLoading(args));

    await waitFor(() => {
      expect(args.setApiError).toHaveBeenCalledWith(
        expect.stringContaining("Could not load conversation"),
      );
    });
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
    const { rerender } = renderHook(() => useUnifiedChatDataLoading(args));

    // Wait for both attempts to fail
    await waitFor(() => {
      expect(mockGetStrategy).toHaveBeenCalledTimes(2);
      expect(args.setApiError).toHaveBeenCalledWith(
        expect.stringContaining("Could not load conversation"),
      );
    });

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
    mockGetStrategy.mockResolvedValueOnce(strategyWithSteps);
    const args = makeArgs();

    renderHook(() => useUnifiedChatDataLoading(args));

    await waitFor(() => {
      expect(mockGetStrategy).toHaveBeenCalledTimes(1);
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

    const { result } = renderHook(() => useUnifiedChatDataLoading(args));

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

  it("does NOT retry when authVersion bumps if the load succeeded", async () => {
    // Successful load
    mockGetStrategy.mockResolvedValueOnce(mockStrategy);
    const args = makeArgs();

    const { rerender } = renderHook(() => useUnifiedChatDataLoading(args));

    await waitFor(() => {
      expect(mockGetStrategy).toHaveBeenCalledTimes(1);
    });

    // Bump authVersion — should NOT trigger a retry since load succeeded
    mockAuthVersion = 1;

    await act(async () => {
      rerender();
    });

    // Give it time to settle — should still be only 1 call
    await new Promise((r) => setTimeout(r, 50));
    expect(mockGetStrategy).toHaveBeenCalledTimes(1);
  });
});
