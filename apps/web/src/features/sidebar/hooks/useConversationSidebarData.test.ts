/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
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

// Track the latest state returned by the fetching mock so tests can
// dynamically update it (e.g. simulate a fetch completing).
let fetchingState: Record<string, unknown> = {};

vi.mock("@/features/sidebar/hooks/useStrategyFetching", () => ({
  useStrategyFetching: () => fetchingState,
}));

function makeArgs() {
  return {
    siteId: "plasmodb",
  };
}

function initFetchingState(overrides: Partial<typeof fetchingState> = {}) {
  fetchingState = {
    strategies: [],
    dismissedStrategies: [],
    isLoading: false,
    isFetched: false,
    isSyncing: false,
    invalidate: vi.fn().mockResolvedValue(undefined),
    handleManualRefresh: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

describe("useConversationSidebarData", () => {
  beforeEach(() => {
    initFetchingState();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows hasInitiallyLoaded=false until the first fetch completes", () => {
    initFetchingState({ isFetched: false });

    const { result } = renderHook(() => useConversationSidebarData(makeArgs()));

    expect(result.current.hasInitiallyLoaded).toBe(false);
  });

  it("populates filtered list after fetch", () => {
    initFetchingState({
      strategies: [fakeStrategy],
      isFetched: true,
    });

    const { result } = renderHook(() => useConversationSidebarData(makeArgs()));

    expect(result.current.filtered).toHaveLength(1);
    expect(result.current.filtered[0]!.id).toBe("s1");
  });

  it("shows empty list when fetch returns no strategies", () => {
    initFetchingState({
      strategies: [],
      isFetched: true,
    });

    const { result } = renderHook(() => useConversationSidebarData(makeArgs()));

    expect(result.current.hasInitiallyLoaded).toBe(true);
    expect(result.current.filtered).toHaveLength(0);
  });

  it("filters conversations by search query", () => {
    initFetchingState({
      strategies: [
        fakeStrategy,
        { ...fakeStrategy, id: "s2", name: "Gene Analysis" },
      ],
      isFetched: true,
    });

    const { result } = renderHook(() => useConversationSidebarData(makeArgs()));

    // All items visible before search
    expect(result.current.filtered).toHaveLength(2);

    // Apply search filter
    act(() => {
      result.current.setQuery("gene");
    });

    expect(result.current.filtered).toHaveLength(1);
    expect(result.current.filtered[0]!.id).toBe("s2");
  });

  it("maps dismissed items to ConversationItem[]", () => {
    const dismissedStrategy: Strategy = {
      ...fakeStrategy,
      id: "dismissed-1",
      name: "Old Strategy",
    };
    initFetchingState({
      dismissedStrategies: [dismissedStrategy],
      isFetched: true,
    });

    const { result } = renderHook(() => useConversationSidebarData(makeArgs()));

    expect(result.current.dismissedConversations).toHaveLength(1);
    expect(result.current.dismissedConversations[0]!.id).toBe("dismissed-1");
    expect(result.current.dismissedConversations[0]!.kind).toBe("strategy");
  });
});
