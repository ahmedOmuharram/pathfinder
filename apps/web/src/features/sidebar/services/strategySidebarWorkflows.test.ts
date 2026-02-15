import { describe, expect, it, vi } from "vitest";
import type { StrategyListItem } from "@/features/sidebar/utils/strategyItems";
import { runDeleteStrategyWorkflow } from "@/features/sidebar/services/strategySidebarWorkflows";

describe("strategySidebarWorkflows", () => {
  it("runDeleteStrategyWorkflow optimistically removes and clears active strategy", async () => {
    const item = {
      id: "s1",
      name: "A",
      updatedAt: "",
      isSaved: false,
    } as StrategyListItem;
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
    const refreshStrategies = vi.fn();
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
      refreshStrategies,
      reportError,
    });

    expect(clearStrategy).toHaveBeenCalled();
    expect(removeStrategy).toHaveBeenCalledWith("s1");
    expect(setStrategyId).toHaveBeenCalledWith(null);
    expect(deleteStrategyApi).toHaveBeenCalledWith("s1");
    expect(refreshStrategies).toHaveBeenCalled();
    expect(reportError).not.toHaveBeenCalled();
  });
});
