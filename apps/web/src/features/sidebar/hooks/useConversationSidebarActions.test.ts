/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { createTestWrapper } from "@/lib/query/testing";
import { strategiesListOptions, dismissedStrategiesOptions } from "@/lib/api/strategies";
import type { Strategy } from "@pathfinder/shared";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";

// ---------------------------------------------------------------------------
// Mock fns — hoisted so vi.mock factories can reference them
// ---------------------------------------------------------------------------

const mockOpenStrategy = vi.hoisted(() => vi.fn());
const mockUpdateStrategy = vi.hoisted(() => vi.fn());
const mockDeleteStrategy = vi.hoisted(() => vi.fn());
const mockRestoreStrategy = vi.hoisted(() => vi.fn());
const mockGetStrategy = vi.hoisted(() => vi.fn());

const mockSetStrategyId = vi.hoisted(() => vi.fn());
const mockBumpChatPreviewVersion = vi.hoisted(() => vi.fn());
const mockSetStrategyMeta = vi.hoisted(() => vi.fn());
const mockSetStrategy = vi.hoisted(() => vi.fn());
const mockClearStrategy = vi.hoisted(() => vi.fn());
const mockSetDeleteFromWdk = vi.hoisted(() => vi.fn());

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/api/strategies", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/strategies")>();
  return {
    ...actual,
    openStrategy: (...args: unknown[]) => mockOpenStrategy(...args),
    updateStrategy: (...args: unknown[]) => mockUpdateStrategy(...args),
    deleteStrategy: (...args: unknown[]) => mockDeleteStrategy(...args),
    restoreStrategy: (...args: unknown[]) => mockRestoreStrategy(...args),
    getStrategy: (...args: unknown[]) => mockGetStrategy(...args),
  };
});

let mockStrategyId: string | null = null;

vi.mock("@/state/useSessionStore", () => ({
  useSessionStore: <T>(
    selector: (s: {
      strategyId: string | null;
      setStrategyId: (id: string | null) => void;
      bumpChatPreviewVersion: () => void;
    }) => T,
  ) =>
    selector({
      strategyId: mockStrategyId,
      setStrategyId: mockSetStrategyId,
      bumpChatPreviewVersion: mockBumpChatPreviewVersion,
    }),
}));

vi.mock("@/state/strategy/store", () => ({
  useStrategyStore: <T>(
    selector: (s: {
      setStrategyMeta: (updates: Partial<Strategy>) => void;
      setStrategy: (strategy: Strategy | null) => void;
      clear: () => void;
    }) => T,
  ) =>
    selector({
      setStrategyMeta: mockSetStrategyMeta,
      setStrategy: mockSetStrategy,
      clear: mockClearStrategy,
    }),
}));

let mockDeleteFromWdk = false;

vi.mock("@/state/useSettingsStore", () => ({
  useSettingsStore: <T>(
    selector: (s: {
      deleteFromWdk: boolean;
      setDeleteFromWdk: (v: boolean) => void;
    }) => T,
  ) =>
    selector({
      deleteFromWdk: mockDeleteFromWdk,
      setDeleteFromWdk: mockSetDeleteFromWdk,
    }),
}));

vi.mock("@/lib/api/errors", () => ({
  toUserMessage: (_err: unknown, fallback: string) => fallback,
}));

// ---------------------------------------------------------------------------
// Imports under test (AFTER mocks)
// ---------------------------------------------------------------------------

import { useConversationSidebarActions } from "./useConversationSidebarActions";
import { useDeleteWorkflow } from "./useDeleteWorkflow";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SITE_ID = "plasmodb";
const NOW = "2026-01-15T12:00:00.000Z";

function makeStrategy(overrides: Partial<Strategy> & { id: string }): Strategy {
  return {
    name: "Test Strategy",
    siteId: SITE_ID,
    recordType: "transcript",
    steps: [],
    rootStepId: null,
    isSaved: false,
    createdAt: NOW,
    updatedAt: NOW,
    stepCount: 0,
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

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useConversationSidebarActions", () => {
  const reportError = vi.fn();
  const setNewConversationInFlight = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockStrategyId = null;
    mockDeleteFromWdk = false;
  });

  // =========================================================================
  // 1. handleNewConversation creates strategy and adds to cache
  // =========================================================================

  it("handleNewConversation creates strategy and adds to cache", async () => {
    const { queryClient, Wrapper } = createTestWrapper();

    const existing = makeStrategy({ id: "existing-1", name: "Existing" });
    queryClient.setQueryData(
      strategiesListOptions(SITE_ID).queryKey,
      [existing],
    );

    mockOpenStrategy.mockResolvedValueOnce({ strategyId: "new-123" });

    const { result } = renderHook(
      () =>
        useConversationSidebarActions({
          siteId: SITE_ID,
          reportError,
          setNewConversationInFlight,
        }),
      { wrapper: Wrapper },
    );

    await act(async () => {
      await result.current.handleNewConversation();
    });

    // Cache now has 2 strategies, with the new one first.
    const cached = queryClient.getQueryData<Strategy[]>(
      strategiesListOptions(SITE_ID).queryKey,
    );
    expect(cached).toHaveLength(2);
    expect(cached![0]!.id).toBe("new-123");
    expect(cached![1]!.id).toBe("existing-1");

    // setStrategyId was called with the new id.
    expect(mockSetStrategyId).toHaveBeenCalledWith("new-123");
    expect(mockBumpChatPreviewVersion).toHaveBeenCalledTimes(1);

    // clearStrategy was called to reset graph state.
    expect(mockClearStrategy).toHaveBeenCalled();

    // In-flight signals were toggled.
    expect(setNewConversationInFlight).toHaveBeenCalledWith(true);
    expect(setNewConversationInFlight).toHaveBeenCalledWith(false);
  });

  // =========================================================================
  // 2. handleToggleSaved updates isSaved in cache after API resolves
  // =========================================================================

  it("handleToggleSaved updates isSaved in cache", async () => {
    const { queryClient, Wrapper } = createTestWrapper();

    const s1 = makeStrategy({ id: "s1", isSaved: false });
    queryClient.setQueryData(
      strategiesListOptions(SITE_ID).queryKey,
      [s1],
    );

    // updateStrategy resolves with the updated strategy.
    mockUpdateStrategy.mockResolvedValueOnce(
      makeStrategy({ id: "s1", isSaved: true }),
    );

    const { result } = renderHook(
      () =>
        useConversationSidebarActions({
          siteId: SITE_ID,
          reportError,
          setNewConversationInFlight,
        }),
      { wrapper: Wrapper },
    );

    await act(async () => {
      await result.current.handleToggleSaved(s1);
    });

    // Cache should reflect isSaved: true.
    const cached = queryClient.getQueryData<Strategy[]>(
      strategiesListOptions(SITE_ID).queryKey,
    );
    expect(cached).toHaveLength(1);
    expect(cached![0]!.isSaved).toBe(true);

    // API was called with the toggled value.
    expect(mockUpdateStrategy).toHaveBeenCalledWith("s1", { isSaved: true });
  });

  it("handleSelect bumps the chat preview before switching conversations", async () => {
    const { Wrapper } = createTestWrapper();
    const selected = makeStrategy({ id: "picked-1", name: "Picked strategy" });
    mockGetStrategy.mockResolvedValueOnce(selected);

    const { result } = renderHook(
      () =>
        useConversationSidebarActions({
          siteId: SITE_ID,
          reportError,
          setNewConversationInFlight,
        }),
      { wrapper: Wrapper },
    );

    act(() => {
      result.current.handleSelect(makeConversationItem(selected));
    });

    await waitFor(() => {
      expect(mockGetStrategy).toHaveBeenCalledWith("picked-1");
    });

    expect(mockBumpChatPreviewVersion).toHaveBeenCalledTimes(1);
    expect(mockSetStrategyId).toHaveBeenCalledWith("picked-1");
    expect(mockClearStrategy).toHaveBeenCalled();
  });

  // =========================================================================
  // 3. confirmDelete removes strategy from cache optimistically
  // =========================================================================

  it("confirmDelete removes strategy from cache optimistically", async () => {
    const { queryClient, Wrapper } = createTestWrapper();

    const s1 = makeStrategy({ id: "s1", name: "Keep" });
    const s2 = makeStrategy({ id: "s2", name: "Delete Me" });
    queryClient.setQueryData(
      strategiesListOptions(SITE_ID).queryKey,
      [s1, s2],
    );

    // deleteStrategy will resolve (no soft-delete, no WDK link).
    mockDeleteStrategy.mockResolvedValueOnce(undefined);

    const { result } = renderHook(
      () => useDeleteWorkflow({ siteId: SITE_ID, reportError }),
      { wrapper: Wrapper },
    );

    // Set the delete target.
    act(() => {
      result.current.setDeleteTarget({
        id: "s2",
        kind: "strategy",
        title: "Delete Me",
        updatedAt: NOW,
        strategyItem: s2,
      });
    });

    await act(async () => {
      await result.current.confirmDelete();
    });

    // Cache should immediately have only 1 strategy (s1).
    const cached = queryClient.getQueryData<Strategy[]>(
      strategiesListOptions(SITE_ID).queryKey,
    );
    expect(cached).toHaveLength(1);
    expect(cached![0]!.id).toBe("s1");

    // deleteStrategy was called.
    expect(mockDeleteStrategy).toHaveBeenCalledWith("s2", false);
  });

  // =========================================================================
  // 4. confirmDelete rolls back on API error
  // =========================================================================

  it("confirmDelete rolls back dismissed list on API error", async () => {
    const { queryClient, Wrapper } = createTestWrapper();

    // Strategy has a wdkStrategyId so it goes through soft-delete (dismiss) path.
    const s1 = makeStrategy({
      id: "s1",
      name: "WDK Strategy",
      wdkStrategyId: 42,
    });
    queryClient.setQueryData(
      strategiesListOptions(SITE_ID).queryKey,
      [s1],
    );
    queryClient.setQueryData(
      dismissedStrategiesOptions(SITE_ID).queryKey,
      [],
    );

    // deleteFromWdk is false, so the strategy will be "dismissed" (soft-deleted).
    mockDeleteFromWdk = false;

    // deleteStrategy rejects.
    mockDeleteStrategy.mockRejectedValueOnce(new Error("server error"));

    const { result } = renderHook(
      () => useDeleteWorkflow({ siteId: SITE_ID, reportError }),
      { wrapper: Wrapper },
    );

    act(() => {
      result.current.setDeleteTarget({
        id: "s1",
        kind: "strategy",
        title: "WDK Strategy",
        updatedAt: NOW,
        strategyItem: s1,
      });
    });

    // Before confirmDelete: dismissed list is empty.
    expect(
      queryClient.getQueryData<Strategy[]>(
        dismissedStrategiesOptions(SITE_ID).queryKey,
      ),
    ).toHaveLength(0);

    await act(async () => {
      await result.current.confirmDelete();
    });

    // After API error: dismissed list should be rolled back to empty
    // (the optimistic add of s1 was reverted).
    const dismissed = queryClient.getQueryData<Strategy[]>(
      dismissedStrategiesOptions(SITE_ID).queryKey,
    );
    expect(dismissed).toHaveLength(0);

    // reportError was called.
    expect(reportError).toHaveBeenCalledWith(
      "Failed to delete strategy. Please try again.",
    );
  });

  // =========================================================================
  // 5. handleRestore moves strategy from dismissed to active list
  // =========================================================================

  it("handleRestore moves strategy from dismissed to active list", async () => {
    const { queryClient, Wrapper } = createTestWrapper();

    const s1 = makeStrategy({ id: "s1", name: "Dismissed Strategy" });

    // Pre-populate dismissed cache with 1 strategy, active is empty.
    queryClient.setQueryData(
      dismissedStrategiesOptions(SITE_ID).queryKey,
      [s1],
    );
    queryClient.setQueryData(
      strategiesListOptions(SITE_ID).queryKey,
      [],
    );

    // restoreStrategy API returns the restored strategy.
    mockRestoreStrategy.mockResolvedValueOnce(s1);

    const { result } = renderHook(
      () => useDeleteWorkflow({ siteId: SITE_ID, reportError }),
      { wrapper: Wrapper },
    );

    await act(async () => {
      await result.current.handleRestore("s1");
    });

    // Dismissed cache should be empty.
    const dismissed = queryClient.getQueryData<Strategy[]>(
      dismissedStrategiesOptions(SITE_ID).queryKey,
    );
    expect(dismissed).toHaveLength(0);

    // Active list should have the restored strategy.
    const active = queryClient.getQueryData<Strategy[]>(
      strategiesListOptions(SITE_ID).queryKey,
    );
    expect(active).toHaveLength(1);
    expect(active![0]!.id).toBe("s1");
    expect(active![0]!.name).toBe("Dismissed Strategy");

    // restoreStrategy was called with the right id.
    expect(mockRestoreStrategy).toHaveBeenCalledWith("s1");
  });
});
