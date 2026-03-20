/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import type { Strategy } from "@pathfinder/shared";
import { useConversationSidebarData } from "./useConversationSidebarData";

// --- Mocks ---

const fakeStrategy: Strategy = {
  id: "s1",
  name: "Test Strategy",
  siteId: "plasmodb",
  recordType: null,
  steps: [],
  rootStepId: null,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
  isSaved: false,
};

let mockSyncWdkStrategies: ReturnType<typeof vi.fn>;
let mockOpenStrategy: ReturnType<typeof vi.fn>;
let mockListDismissedStrategies: ReturnType<typeof vi.fn>;
let mockListStrategies: ReturnType<typeof vi.fn>;

vi.mock("@/lib/api/strategies", () => ({
  get syncWdkStrategies() {
    return mockSyncWdkStrategies;
  },
  get openStrategy() {
    return mockOpenStrategy;
  },
  get listDismissedStrategies() {
    return mockListDismissedStrategies;
  },
  get listStrategies() {
    return mockListStrategies;
  },
}));

// Minimal session store mock
let mockSessionState: Record<string, unknown> = {};
vi.mock("@/state/useSessionStore", () => ({
  useSessionStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector(mockSessionState),
}));

// Minimal strategy store mock
let mockStrategyStoreState: Record<string, unknown> = {};
vi.mock("@/state/strategy/store", () => {
  const store = {
    getState: () => ({
      setStrategies: vi.fn(),
      ...mockStrategyStoreState,
    }),
  };
  return {
    useStrategyStore: Object.assign(
      (selector: (s: Record<string, unknown>) => unknown) =>
        selector(mockStrategyStoreState),
      store,
    ),
  };
});

function makeArgs() {
  return {
    siteId: "plasmodb",
    reportError: vi.fn(),
  };
}

describe("useConversationSidebarData", () => {
  beforeEach(() => {
    mockSyncWdkStrategies = vi.fn();
    mockOpenStrategy = vi.fn();
    mockListDismissedStrategies = vi.fn().mockResolvedValue([]);
    mockListStrategies = vi.fn().mockResolvedValue([]);
    mockSessionState = {
      strategyId: null,
      setStrategyId: vi.fn(),
      authVersion: 0,
      veupathdbSignedIn: true,
    };
    mockStrategyStoreState = {
      strategy: null,
      setStrategies: vi.fn(),
    };
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows hasInitiallyLoaded=false until the first fetch completes", async () => {
    let resolveFetch!: (strategies: Strategy[]) => void;
    mockSyncWdkStrategies.mockReturnValueOnce(
      new Promise<Strategy[]>((r) => {
        resolveFetch = r;
      }),
    );

    const { result } = renderHook(() => useConversationSidebarData(makeArgs()));

    // Before fetch completes: not loaded yet
    expect(result.current.hasInitiallyLoaded).toBe(false);

    // Resolve
    await act(async () => {
      resolveFetch([fakeStrategy]);
    });

    await waitFor(() => {
      expect(result.current.hasInitiallyLoaded).toBe(true);
    });
  });

  it("populates filtered list after fetch", async () => {
    mockSyncWdkStrategies.mockResolvedValueOnce([fakeStrategy]);

    const { result } = renderHook(() => useConversationSidebarData(makeArgs()));

    await waitFor(() => {
      expect(result.current.filtered).toHaveLength(1);
      expect(result.current.filtered[0]!.id).toBe("s1");
    });
  });

  it("shows empty list when fetch returns no strategies", async () => {
    mockSyncWdkStrategies.mockResolvedValueOnce([]);
    // Auto-create would fire, mock it too
    mockOpenStrategy.mockResolvedValueOnce({ strategyId: "new-1" });

    const { result } = renderHook(() => useConversationSidebarData(makeArgs()));

    await waitFor(() => {
      expect(result.current.hasInitiallyLoaded).toBe(true);
    });
  });
});
