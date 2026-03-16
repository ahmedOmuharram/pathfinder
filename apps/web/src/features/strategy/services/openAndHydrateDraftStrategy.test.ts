import { describe, expect, it, vi } from "vitest";
import type { Strategy } from "@pathfinder/shared";
import { openAndHydrateDraftStrategy } from "@/features/strategy/services/openAndHydrateDraftStrategy";

describe("openAndHydrateDraftStrategy", () => {
  it("opens, seeds list store, hydrates full strategy, and sets meta", async () => {
    const nowIso = () => "2026-01-01T00:00:00.000Z";
    const open = vi.fn().mockResolvedValue({ strategyId: "s1" });
    const full: Strategy = {
      id: "s1",
      name: "X",
      siteId: "plasmodb",
      recordType: "gene",
      steps: [],
      rootStepId: null,
      isSaved: false,
      createdAt: "t",
      updatedAt: "t",
    };
    const getStrategy = vi.fn().mockResolvedValue(full);

    const setStrategyId = vi.fn();
    const addStrategy = vi.fn();
    const clearStrategy = vi.fn();
    const setStrategy = vi.fn();
    const setStrategyMeta = vi.fn();

    const res = await openAndHydrateDraftStrategy({
      siteId: "plasmodb",
      open,
      getStrategy,
      nowIso,
      setStrategyId,
      addStrategy,
      clearStrategy,
      setStrategy,
      setStrategyMeta,
    });

    expect(res.strategyId).toBe("s1");
    expect(open).toHaveBeenCalledTimes(1);
    expect(setStrategyId).toHaveBeenCalledWith("s1");
    expect(addStrategy).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "s1",
        siteId: "plasmodb",
        name: "New Conversation",
        stepCount: 0,
        createdAt: "2026-01-01T00:00:00.000Z",
      }),
    );
    expect(clearStrategy).toHaveBeenCalled();
    expect(getStrategy).toHaveBeenCalledWith("s1");
    expect(setStrategy).toHaveBeenCalledWith(full);
    expect(setStrategyMeta).toHaveBeenCalledWith({
      name: "X",
      recordType: "gene",
      siteId: "plasmodb",
    });
  });

  it("invokes cleanup callbacks and clears strategy on hydrate error", async () => {
    const nowIso = () => "2026-01-01T00:00:00.000Z";
    const open = vi.fn().mockResolvedValue({ strategyId: "s2" });
    const err = new Error("boom");
    const getStrategy = vi.fn().mockRejectedValue(err);

    const setStrategyId = vi.fn();
    const addStrategy = vi.fn();
    const clearStrategy = vi.fn();
    const setStrategy = vi.fn();
    const setStrategyMeta = vi.fn();
    const onHydrateError = vi.fn();
    const cleanupOnHydrateError = vi.fn();

    await expect(
      openAndHydrateDraftStrategy({
        siteId: "plasmodb",
        open,
        getStrategy,
        nowIso,
        setStrategyId,
        addStrategy,
        clearStrategy,
        setStrategy,
        setStrategyMeta,
        onHydrateError,
        cleanupOnHydrateError,
      }),
    ).rejects.toBe(err);

    expect(onHydrateError).toHaveBeenCalledWith(err, "s2");
    expect(cleanupOnHydrateError).toHaveBeenCalledWith("s2");
    expect(clearStrategy).toHaveBeenCalled();
    expect(setStrategy).not.toHaveBeenCalled();
    expect(setStrategyMeta).not.toHaveBeenCalled();
  });
});
