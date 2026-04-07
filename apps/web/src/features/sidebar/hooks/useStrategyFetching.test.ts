/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import type { Strategy } from "@pathfinder/shared";
import { createTestWrapper } from "@/lib/query/testing";
import { useStrategyFetching } from "./useStrategyFetching";

// ---------------------------------------------------------------------------
// Mock data — realistic Strategy shapes
// ---------------------------------------------------------------------------

const strategyA: Strategy = {
  id: "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
  name: "Genes by GO term",
  siteId: "plasmodb",
  recordType: "transcript",
  steps: [],
  rootStepId: null,
  isSaved: false,
  createdAt: "2026-04-06T12:00:00Z",
  updatedAt: "2026-04-06T12:00:00Z",
};

const strategyB: Strategy = {
  id: "f6e5d4c3-b2a1-4987-8765-fedcba987654",
  name: "Genes by location",
  siteId: "plasmodb",
  recordType: "transcript",
  steps: [],
  rootStepId: null,
  isSaved: true,
  createdAt: "2026-04-05T08:00:00Z",
  updatedAt: "2026-04-06T09:30:00Z",
};

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

let mockSyncWdkStrategies: ReturnType<typeof vi.fn<(siteId: string) => Promise<Strategy[]>>>;
let mockListDismissedStrategies: ReturnType<typeof vi.fn<(siteId: string) => Promise<Strategy[]>>>;

vi.mock("@/lib/api/strategies", () => ({
  strategiesListOptions: (siteId: string) => ({
    queryKey: ["strategies", "list", siteId] as const,
    get queryFn() {
      return () => mockSyncWdkStrategies(siteId);
    },
  }),
  dismissedStrategiesOptions: (siteId: string) => ({
    queryKey: ["strategies", "dismissed", siteId] as const,
    get queryFn() {
      return () => mockListDismissedStrategies(siteId);
    },
  }),
}));

// Mock store state
let mockAuthStatusKnown = true;
let mockVeupathdbSignedIn = true;
let mockDraftStrategy: Strategy | null = null;

vi.mock("@/state/useSessionStore", () => ({
  useSessionStore: (
    selector: (s: { veupathdbSignedIn: boolean; authStatusKnown: boolean }) => unknown,
  ) => selector({ veupathdbSignedIn: mockVeupathdbSignedIn, authStatusKnown: mockAuthStatusKnown }),
}));

vi.mock("@/state/strategy/store", () => ({
  useStrategyStore: (selector: (s: { strategy: Strategy | null }) => unknown) =>
    selector({ strategy: mockDraftStrategy }),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useStrategyFetching", () => {
  beforeEach(() => {
    mockSyncWdkStrategies = vi.fn().mockResolvedValue([]);
    mockListDismissedStrategies = vi.fn().mockResolvedValue([]);
    mockAuthStatusKnown = true;
    mockVeupathdbSignedIn = true;
    mockDraftStrategy = null;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches strategies for a given siteId", async () => {
    mockSyncWdkStrategies.mockResolvedValue([strategyA, strategyB]);

    const { Wrapper } = createTestWrapper();
    const reportError = vi.fn();

    const { result } = renderHook(
      () => useStrategyFetching({ siteId: "plasmodb", reportError }),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(result.current.strategies).toHaveLength(2);
    });

    expect(result.current.strategies[0]!.name).toBe("Genes by GO term");
    expect(result.current.strategies[0]!.siteId).toBe("plasmodb");
    expect(result.current.strategies[1]!.name).toBe("Genes by location");
    expect(mockSyncWdkStrategies).toHaveBeenCalledWith("plasmodb");
  });

  it("returns empty when siteId is empty", async () => {
    const { Wrapper } = createTestWrapper();
    const reportError = vi.fn();

    const { result } = renderHook(
      () => useStrategyFetching({ siteId: "", reportError }),
      { wrapper: Wrapper },
    );

    // Query is disabled so strategies stays empty and the API is never called.
    // Allow a tick for any pending microtasks.
    await waitFor(() => {
      expect(result.current.isFetched).toBe(false);
    });

    expect(result.current.strategies).toEqual([]);
    expect(mockSyncWdkStrategies).not.toHaveBeenCalled();
  });

  it("returns empty when not authenticated", async () => {
    mockAuthStatusKnown = true;
    mockVeupathdbSignedIn = false;

    const { Wrapper } = createTestWrapper();
    const reportError = vi.fn();

    const { result } = renderHook(
      () => useStrategyFetching({ siteId: "plasmodb", reportError }),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(result.current.isFetched).toBe(false);
    });

    expect(result.current.strategies).toEqual([]);
    expect(mockSyncWdkStrategies).not.toHaveBeenCalled();
  });

  it("handleManualRefresh sets isSyncing then clears it", async () => {
    mockSyncWdkStrategies.mockResolvedValue([strategyA]);

    const { Wrapper, queryClient } = createTestWrapper();
    const reportError = vi.fn();

    const { result } = renderHook(
      () => useStrategyFetching({ siteId: "plasmodb", reportError }),
      { wrapper: Wrapper },
    );

    // Wait for initial load to complete
    await waitFor(() => {
      expect(result.current.strategies).toHaveLength(1);
    });

    // Prepare a slow second fetch so we can observe isSyncing=true
    let resolveRefresh!: (value: Strategy[]) => void;
    mockSyncWdkStrategies.mockReturnValueOnce(
      new Promise<Strategy[]>((r) => {
        resolveRefresh = r;
      }),
    );
    // dismissed also needs to resolve
    mockListDismissedStrategies.mockReturnValueOnce(
      new Promise<Strategy[]>((r) => {
        // Resolve immediately — we only gate on the strategies query
        r([]);
      }),
    );

    // Trigger manual refresh
    let refreshPromise: Promise<void>;
    act(() => {
      refreshPromise = result.current.handleManualRefresh();
    });

    // isSyncing should be true while the invalidation is in-flight
    expect(result.current.isSyncing).toBe(true);

    // Resolve the pending fetch
    await act(async () => {
      resolveRefresh([strategyA, strategyB]);
      await refreshPromise;
    });

    expect(result.current.isSyncing).toBe(false);
  });

  it("reports errors from a failed fetch", async () => {
    mockSyncWdkStrategies.mockRejectedValue(new Error("WDK unreachable"));

    const { Wrapper } = createTestWrapper();
    const reportError = vi.fn();

    renderHook(
      () => useStrategyFetching({ siteId: "plasmodb", reportError }),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(reportError).toHaveBeenCalledWith("WDK unreachable");
    });
  });
});
