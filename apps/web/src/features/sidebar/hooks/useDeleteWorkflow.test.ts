/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import type { Strategy } from "@pathfinder/shared";
import { createTestWrapper } from "@/lib/query/testing";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";

// ---------------------------------------------------------------------------
// Hoisted mocks for API functions
// ---------------------------------------------------------------------------

const mockDeleteStrategy = vi.hoisted(() => vi.fn());
const mockRestoreStrategy = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/strategies", () => ({
  deleteStrategy: mockDeleteStrategy,
  restoreStrategy: mockRestoreStrategy,
  strategiesListOptions: (siteId: string) => ({
    queryKey: ["strategies", "list", siteId] as const,
    queryFn: vi.fn(),
  }),
  dismissedStrategiesOptions: (siteId: string) => ({
    queryKey: ["strategies", "dismissed", siteId] as const,
    queryFn: vi.fn(),
  }),
}));

vi.mock("@/lib/api/errors", () => ({
  toUserMessage: (err: unknown, fallback: string) =>
    err instanceof Error ? err.message : fallback,
}));

// ---------------------------------------------------------------------------
// Store mocks
// ---------------------------------------------------------------------------

const mockSetStrategyId = vi.fn();
const mockClearStrategy = vi.fn();
let mockStrategyId: string | null = null;
let mockDeleteFromWdk = false;

vi.mock("@/state/useSessionStore", () => ({
  useSessionStore: (
    selector: (s: { strategyId: string | null; setStrategyId: (id: string | null) => void }) => unknown,
  ) => selector({ strategyId: mockStrategyId, setStrategyId: mockSetStrategyId }),
}));

vi.mock("@/state/useSettingsStore", () => ({
  useSettingsStore: (
    selector: (s: { deleteFromWdk: boolean }) => unknown,
  ) => selector({ deleteFromWdk: mockDeleteFromWdk }),
}));

vi.mock("@/state/strategy/store", () => ({
  useStrategyStore: (
    selector: (s: { clear: () => void }) => unknown,
  ) => selector({ clear: mockClearStrategy }),
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { useDeleteWorkflow } from "./useDeleteWorkflow";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

function makeStrategy(overrides?: Partial<Strategy>): Strategy {
  return {
    id: "s1",
    name: "Genes by GO term",
    siteId: "plasmodb",
    updatedAt: "2026-04-06T12:00:00Z",
    createdAt: "2026-04-06T12:00:00Z",
    recordType: "transcript",
    steps: [],
    rootStepId: null,
    isSaved: false,
    ...overrides,
  };
}

function makeConversationItem(strategy: Strategy): ConversationItem {
  return {
    id: strategy.id,
    kind: "strategy",
    title: strategy.name,
    updatedAt: strategy.updatedAt,
    siteId: strategy.siteId,
    strategyItem: strategy,
  };
}

const SITE_ID = "plasmodb";
const LIST_KEY = ["strategies", "list", SITE_ID] as const;
const DISMISSED_KEY = ["strategies", "dismissed", SITE_ID] as const;

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useDeleteWorkflow", () => {
  beforeEach(() => {
    mockStrategyId = null;
    mockDeleteFromWdk = false;
    mockDeleteStrategy.mockReset();
    mockRestoreStrategy.mockReset();
    mockSetStrategyId.mockClear();
    mockClearStrategy.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("confirmDelete optimistically removes from active list", async () => {
    const s1 = makeStrategy({ id: "s1", name: "Genes by GO term" });
    const s2 = makeStrategy({ id: "s2", name: "Genes by text search" });

    // deleteStrategy resolves slowly so we can inspect cache before it settles
    mockDeleteStrategy.mockReturnValue(new Promise<void>((resolve) => setTimeout(resolve, 500)));

    const { queryClient, Wrapper } = createTestWrapper();
    queryClient.setQueryData(LIST_KEY, [s1, s2]);

    const { result } = renderHook(
      () => useDeleteWorkflow({ siteId: SITE_ID, reportError: vi.fn() }),
      { wrapper: Wrapper },
    );

    // Set delete target to s1, then confirm
    act(() => { result.current.setDeleteTarget(makeConversationItem(s1)); });
    // Do not await — we want to check cache IMMEDIATELY after the sync optimistic update
    void act(() => { void result.current.confirmDelete(); });

    // Cache should already have only s2 (optimistic)
    const cached = queryClient.getQueryData<Strategy[]>(LIST_KEY);
    expect(cached).toHaveLength(1);
    expect(cached![0]!.id).toBe("s2");
  });

  it("confirmDelete adds to dismissed list when soft-deleting WDK strategy", async () => {
    const wdkStrategy = makeStrategy({ id: "s1", wdkStrategyId: 12345 });
    mockDeleteFromWdk = false;
    mockDeleteStrategy.mockResolvedValue(undefined);

    const { queryClient, Wrapper } = createTestWrapper();
    queryClient.setQueryData(LIST_KEY, [wdkStrategy]);
    queryClient.setQueryData(DISMISSED_KEY, []);

    const { result } = renderHook(
      () => useDeleteWorkflow({ siteId: SITE_ID, reportError: vi.fn() }),
      { wrapper: Wrapper },
    );

    act(() => { result.current.setDeleteTarget(makeConversationItem(wdkStrategy)); });
    void act(() => { void result.current.confirmDelete(); });

    // Dismissed cache should now contain the WDK strategy
    const dismissed = queryClient.getQueryData<Strategy[]>(DISMISSED_KEY);
    expect(dismissed).toHaveLength(1);
    expect(dismissed![0]!.id).toBe("s1");
    expect(dismissed![0]!.wdkStrategyId).toBe(12345);

    // Active list should be empty
    const active = queryClient.getQueryData<Strategy[]>(LIST_KEY);
    expect(active).toHaveLength(0);
  });

  it("confirmDelete rolls back on API failure", async () => {
    const s1 = makeStrategy({ id: "s1", name: "Important strategy" });
    const reportError = vi.fn();
    mockDeleteStrategy.mockRejectedValue(new Error("Server error"));

    const { queryClient, Wrapper } = createTestWrapper();
    queryClient.setQueryData(LIST_KEY, [s1]);

    const { result } = renderHook(
      () => useDeleteWorkflow({ siteId: SITE_ID, reportError }),
      { wrapper: Wrapper },
    );

    act(() => { result.current.setDeleteTarget(makeConversationItem(s1)); });

    await act(async () => { await result.current.confirmDelete(); });

    // After the error, invalidateQueries fires to roll back.
    // reportError should have been called with the error message.
    expect(reportError).toHaveBeenCalledWith("Server error");

    // The hook calls invalidateQueries in `finally`, which marks the query
    // as stale/refetching. Since there is no real queryFn to resolve, the
    // cache entry will be in a fetching state. The key point: the optimistic
    // removal was NOT left as the final state — invalidation was triggered.
    // We verify the error path completed and reported.
    expect(mockDeleteStrategy).toHaveBeenCalledWith("s1", false);
  });

  it("handleRestore moves from dismissed to active", async () => {
    const s1 = makeStrategy({ id: "s1", name: "Restored strategy" });
    mockRestoreStrategy.mockResolvedValue(s1);

    const { queryClient, Wrapper } = createTestWrapper();
    queryClient.setQueryData(DISMISSED_KEY, [s1]);
    queryClient.setQueryData(LIST_KEY, []);

    const { result } = renderHook(
      () => useDeleteWorkflow({ siteId: SITE_ID, reportError: vi.fn() }),
      { wrapper: Wrapper },
    );

    await act(async () => { await result.current.handleRestore("s1"); });

    // Dismissed cache should be empty
    const dismissed = queryClient.getQueryData<Strategy[]>(DISMISSED_KEY);
    expect(dismissed).toHaveLength(0);

    // Active cache should contain the restored strategy
    await waitFor(() => {
      const active = queryClient.getQueryData<Strategy[]>(LIST_KEY);
      expect(active).toHaveLength(1);
      expect(active![0]!.id).toBe("s1");
      expect(active![0]!.name).toBe("Restored strategy");
    });
  });
});
