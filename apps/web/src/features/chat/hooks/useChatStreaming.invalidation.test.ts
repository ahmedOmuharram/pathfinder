/**
 * @vitest-environment jsdom
 *
 * Tests that TanStack Query cache invalidation works correctly for the
 * key patterns used by useChatStreaming (strategy list + detail) and
 * workbench panels (experiments prefix).
 *
 * Rather than rendering the full useChatStreaming hook (which has many
 * dependencies), these tests exercise the invalidation pattern directly:
 * pre-populate cache, call invalidateQueries with the same keys the
 * production code uses, and assert the cache state changes.
 */

import { describe, it, expect, vi } from "vitest";
import { createTestWrapper } from "@/lib/query/testing";
import { strategiesListOptions } from "@/lib/api/strategies";
import { queryKeyPrefixes } from "@/lib/query/keys";
import type { Strategy } from "@pathfinder/shared";

// ---------------------------------------------------------------------------
// 1. Strategy list cache invalidated after stream completion
// ---------------------------------------------------------------------------

describe("strategy list cache invalidation", () => {
  it("invalidates the strategy list cache for the active siteId", async () => {
    const { queryClient } = createTestWrapper();
    const siteId = "plasmodb";
    const listKey = strategiesListOptions(siteId).queryKey;

    // Pre-populate cache with stale strategy data.
    const staleStrategy: Strategy = {
      id: "s1",
      name: "Stale Strategy",
      siteId,
      recordType: "transcript",
      steps: [],
      rootStepId: null,
      isSaved: false,
      createdAt: "2026-04-06T12:00:00Z",
      updatedAt: "2026-04-06T12:00:00Z",
    };
    queryClient.setQueryData(listKey, [staleStrategy]);

    // Sanity: cache contains our data.
    expect(queryClient.getQueryData(listKey)).toEqual([staleStrategy]);

    const spy = vi.spyOn(queryClient, "invalidateQueries");

    // Simulate the exact invalidation call from useChatStreaming onComplete.
    await queryClient.invalidateQueries({ queryKey: strategiesListOptions(siteId).queryKey });

    expect(spy).toHaveBeenCalledWith({
      queryKey: ["strategies", "list", "plasmodb"],
    });

    // After invalidation, the query state should be marked as stale/invalidated.
    // Since there is no active observer or queryFn (we used setQueryData), the
    // data remains but the query is marked invalid — getQueryState shows it.
    const state = queryClient.getQueryState(listKey);
    expect(state).toBeDefined();
    expect(state!.isInvalidated).toBe(true);

    spy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// 2. Strategy detail cache invalidated when strategyId is present
// ---------------------------------------------------------------------------

describe("strategy detail cache invalidation via prefix", () => {
  it("invalidates all strategy queries when a strategyId is present", async () => {
    const { queryClient } = createTestWrapper();
    const siteId = "plasmodb";
    const strategyId = "abc-123";

    // Pre-populate both the list cache and a detail cache entry.
    const listKey = strategiesListOptions(siteId).queryKey;
    const detailKey = ["strategies", "detail", strategyId];

    const detailStrategy: Strategy = {
      id: strategyId,
      name: "Detail Test",
      siteId,
      recordType: "transcript",
      steps: [],
      rootStepId: null,
      isSaved: false,
      createdAt: "2026-04-06T12:00:00Z",
      updatedAt: "2026-04-06T12:00:00Z",
    };
    queryClient.setQueryData(listKey, [detailStrategy]);
    queryClient.setQueryData(detailKey, detailStrategy);

    const spy = vi.spyOn(queryClient, "invalidateQueries");

    // Simulate the exact invalidation pattern from useChatStreaming when
    // effectiveStrategyId != null && effectiveStrategyId !== "":
    //   void queryClient.invalidateQueries({ queryKey: queryKeyPrefixes.strategies });
    await queryClient.invalidateQueries({ queryKey: queryKeyPrefixes.strategies });

    expect(spy).toHaveBeenCalledWith({
      queryKey: ["strategies"],
    });

    // The prefix ["strategies"] should match both ["strategies", "list", ...]
    // and ["strategies", "detail", ...] via TanStack Query prefix matching.
    const listState = queryClient.getQueryState(listKey);
    const detailState = queryClient.getQueryState(detailKey);

    expect(listState).toBeDefined();
    expect(listState!.isInvalidated).toBe(true);

    expect(detailState).toBeDefined();
    expect(detailState!.isInvalidated).toBe(true);

    spy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// 3. Experiment cache invalidated after workbench stream completion
// ---------------------------------------------------------------------------

describe("experiment cache invalidation", () => {
  it("invalidates all experiment queries using the experiments prefix key", async () => {
    const { queryClient } = createTestWrapper();

    // Pre-populate experiment cache entries (list + detail).
    const experimentListKey = ["experiments", "list", "plasmodb"];
    const experimentDetailKey = ["experiments", "detail", "exp-42"];

    queryClient.setQueryData(experimentListKey, [
      { id: "exp-42", name: "Evaluation run 1" },
    ]);
    queryClient.setQueryData(experimentDetailKey, {
      id: "exp-42",
      name: "Evaluation run 1",
      metrics: { accuracy: 0.85 },
    });

    // Sanity: both caches populated.
    expect(queryClient.getQueryData(experimentListKey)).toBeDefined();
    expect(queryClient.getQueryData(experimentDetailKey)).toBeDefined();

    const spy = vi.spyOn(queryClient, "invalidateQueries");

    // Simulate the exact invalidation call from EvaluatePanel / BatchPanel /
    // BenchmarkPanel onComplete:
    //   void queryClient.invalidateQueries({ queryKey: queryKeyPrefixes.experiments });
    await queryClient.invalidateQueries({ queryKey: queryKeyPrefixes.experiments });

    expect(spy).toHaveBeenCalledWith({
      queryKey: ["experiments"],
    });

    // Both experiment cache entries should be invalidated via prefix match.
    const listState = queryClient.getQueryState(experimentListKey);
    const detailState = queryClient.getQueryState(experimentDetailKey);

    expect(listState).toBeDefined();
    expect(listState!.isInvalidated).toBe(true);

    expect(detailState).toBeDefined();
    expect(detailState!.isInvalidated).toBe(true);

    spy.mockRestore();
  });
});
