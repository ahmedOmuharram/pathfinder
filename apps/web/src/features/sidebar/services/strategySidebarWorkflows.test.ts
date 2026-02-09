import { describe, expect, it, vi } from "vitest";
import type { StrategyListItem } from "@/features/sidebar/utils/strategyItems";
import {
  runDeleteStrategyWorkflow,
  runPushStrategyWorkflow,
  runSyncFromWdkWorkflow,
} from "@/features/sidebar/services/strategySidebarWorkflows";

describe("strategySidebarWorkflows", () => {
  it("runDeleteStrategyWorkflow optimistically removes and clears active strategy", async () => {
    const item = {
      id: "s1",
      name: "A",
      updatedAt: "",
      source: "draft",
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

  it("runPushStrategyWorkflow reports error on failure", async () => {
    const item = {
      id: "s1",
      name: "A",
      updatedAt: "",
      source: "draft",
    } as StrategyListItem;
    const pushStrategyApi = vi.fn().mockRejectedValue(new Error("boom"));
    const refreshStrategies = vi.fn();
    const reportError = vi.fn();

    await runPushStrategyWorkflow({
      item,
      pushStrategyApi,
      refreshStrategies,
      reportError,
    });

    expect(refreshStrategies).not.toHaveBeenCalled();
    expect(reportError).toHaveBeenCalled();
  });

  it("runSyncFromWdkWorkflow updates active strategy only when ids match", async () => {
    const item = {
      id: "s1",
      name: "A",
      updatedAt: "",
      source: "synced",
      wdkStrategyId: 10,
    } as StrategyListItem;
    const setSyncingStrategyId = vi.fn();
    const syncStrategyFromWdkApi = vi.fn().mockResolvedValue({
      id: "s1",
      name: "New",
      siteId: "plasmodb",
      recordType: "gene",
    } as any);
    const setStrategy = vi.fn();
    const setStrategyMeta = vi.fn();
    const refreshStrategies = vi.fn();
    const reportSuccess = vi.fn();
    const reportError = vi.fn();

    await runSyncFromWdkWorkflow({
      item,
      currentStrategyId: "other",
      setSyncingStrategyId,
      syncStrategyFromWdkApi,
      setStrategy,
      setStrategyMeta,
      refreshStrategies,
      reportSuccess,
      reportError,
    });

    expect(setStrategy).not.toHaveBeenCalled();
    expect(reportSuccess).toHaveBeenCalled();
    expect(refreshStrategies).toHaveBeenCalled();
    expect(setSyncingStrategyId).toHaveBeenLastCalledWith(null);
  });
});
