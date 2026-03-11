import { describe, expect, it, vi } from "vitest";
import type { Strategy } from "@pathfinder/shared";
import { runDeleteStrategyWorkflow } from "@/features/sidebar/services/strategySidebarWorkflows";

describe("strategySidebarWorkflows", () => {
  it("runDeleteStrategyWorkflow optimistically removes and clears active strategy", async () => {
    const item = {
      id: "s1",
      name: "A",
      updatedAt: "",
      isSaved: false,
    } as Strategy;
    const setStrategyItems = vi.fn((updater) => {
      const prev = [item];
      const next = updater(prev);
      expect(next).toEqual([]);
    });
    const clearStrategy = vi.fn();
    const removeStrategy = vi.fn();
    const setStrategyId = vi.fn();
    const setDeleteError = vi.fn();
    const deleteStrategyApi = vi.fn().mockResolvedValue(undefined);
    const refetchStrategies = vi.fn();
    const reportError = vi.fn();

    await runDeleteStrategyWorkflow({
      item,
      currentStrategyId: "s1",
      setStrategyItems,
      clearStrategy,
      removeStrategy,
      setStrategyId,
      setDeleteError,
      deleteStrategyApi,
      deleteFromWdk: false,
      refetchStrategies,
      reportError,
    });

    expect(clearStrategy).toHaveBeenCalled();
    expect(removeStrategy).toHaveBeenCalledWith("s1");
    expect(setStrategyId).toHaveBeenCalledWith(null);
    expect(deleteStrategyApi).toHaveBeenCalledWith("s1", false);
    expect(refetchStrategies).toHaveBeenCalled();
    expect(reportError).not.toHaveBeenCalled();
  });
});
