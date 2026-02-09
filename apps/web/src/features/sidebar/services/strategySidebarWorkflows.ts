import type { StrategyListItem } from "@/features/sidebar/utils/strategyItems";
import type { StrategyWithMeta } from "@/types/strategy";
import { toUserMessage } from "@/lib/api/errors";

export async function runDeleteStrategyWorkflow(args: {
  item: StrategyListItem;
  currentStrategyId: string | null;
  setStrategyItems: (updater: (prev: StrategyListItem[]) => StrategyListItem[]) => void;
  clearStrategy: () => void;
  removeStrategy: (id: string) => void;
  setStrategyId: (id: string | null) => void;
  setDeleteError: (msg: string | null) => void;
  deleteStrategyApi: (id: string) => Promise<void>;
  refreshStrategies: () => void;
  reportError: (msg: string) => void;
}): Promise<void> {
  const {
    item,
    currentStrategyId,
    setStrategyItems,
    clearStrategy,
    removeStrategy,
    setStrategyId,
    setDeleteError,
    deleteStrategyApi,
    refreshStrategies,
    reportError,
  } = args;

  // Optimistic UI removal.
  setStrategyItems((items) => items.filter((entry) => entry.id !== item.id));

  // If deleting active strategy, reset active state.
  if (currentStrategyId === item.id) {
    clearStrategy();
    removeStrategy(item.id);
    setStrategyId(null);
  }

  setDeleteError(null);
  try {
    await deleteStrategyApi(item.id);
  } catch (e) {
    reportError(toUserMessage(e, "Failed to delete strategy. Please try again."));
  } finally {
    refreshStrategies();
  }
}

export async function runPushStrategyWorkflow(args: {
  item: StrategyListItem;
  pushStrategyApi: (id: string) => Promise<unknown>;
  refreshStrategies: () => void;
  reportError: (msg: string) => void;
}): Promise<void> {
  const { item, pushStrategyApi, refreshStrategies, reportError } = args;
  try {
    await pushStrategyApi(item.id);
    refreshStrategies();
  } catch (e) {
    reportError(toUserMessage(e, "Failed to push strategy."));
  }
}

export async function runSyncFromWdkWorkflow(args: {
  item: StrategyListItem;
  currentStrategyId: string | null;
  setSyncingStrategyId: (id: string | null) => void;
  syncStrategyFromWdkApi: (id: string) => Promise<StrategyWithMeta>;
  setStrategy: (s: StrategyWithMeta) => void;
  setStrategyMeta: (meta: {
    name: string;
    recordType?: string;
    siteId: string;
  }) => void;
  refreshStrategies: () => void;
  reportSuccess: (msg: string) => void;
  reportError: (msg: string) => void;
}): Promise<void> {
  const {
    item,
    currentStrategyId,
    setSyncingStrategyId,
    syncStrategyFromWdkApi,
    setStrategy,
    setStrategyMeta,
    refreshStrategies,
    reportSuccess,
    reportError,
  } = args;

  if (!item.wdkStrategyId) {
    reportError("Strategy must be linked to WDK to sync.");
    return;
  }

  setSyncingStrategyId(item.id);
  try {
    const updated = await syncStrategyFromWdkApi(item.id);
    if (currentStrategyId === item.id) {
      setStrategy(updated);
      setStrategyMeta({
        name: updated.name,
        recordType: updated.recordType ?? undefined,
        siteId: updated.siteId,
      });
    }
    reportSuccess(`Synced strategy from WDK (#${item.wdkStrategyId}).`);
    refreshStrategies();
  } catch (e) {
    reportError(toUserMessage(e, "Failed to sync strategy from WDK."));
  } finally {
    setSyncingStrategyId(null);
  }
}
