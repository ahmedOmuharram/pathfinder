import type { Strategy } from "@pathfinder/shared";
import { toUserMessage } from "@/lib/api/errors";

export async function runDeleteStrategyWorkflow(args: {
  item: Strategy;
  currentStrategyId: string | null;
  setStrategyItems: (updater: (prev: Strategy[]) => Strategy[]) => void;
  setDismissedItems?: (updater: (prev: Strategy[]) => Strategy[]) => void;
  clearStrategy: () => void;
  removeStrategy: (id: string) => void;
  setStrategyId: (id: string | null) => void;
  setDeleteError: (msg: string | null) => void;
  deleteStrategyApi: (id: string, deleteFromWdk?: boolean) => Promise<void>;
  deleteFromWdk: boolean;
  refetchStrategies: () => void;
  reportError: (msg: string) => void;
}): Promise<void> {
  const {
    item,
    currentStrategyId,
    setStrategyItems,
    setDismissedItems,
    clearStrategy,
    removeStrategy,
    setStrategyId,
    setDeleteError,
    deleteStrategyApi,
    deleteFromWdk,
    refetchStrategies,
    reportError,
  } = args;

  // Optimistic UI removal from main list.
  setStrategyItems((items) => items.filter((entry) => entry.id !== item.id));

  // For WDK-linked strategies that will be soft-deleted (dismissed), optimistically
  // add to the dismissed list so the UI updates immediately rather than waiting for
  // a refetch (which may be silently dropped by the syncInFlight guard).
  const willSoftDelete = item.wdkStrategyId != null && !deleteFromWdk;
  if (willSoftDelete && setDismissedItems) {
    setDismissedItems((prev) => [...prev, item]);
  }

  // If deleting active strategy, reset active state.
  if (currentStrategyId === item.id) {
    clearStrategy();
    removeStrategy(item.id);
    setStrategyId(null);
  }

  setDeleteError(null);
  try {
    await deleteStrategyApi(item.id, deleteFromWdk);
  } catch (e) {
    // Rollback optimistic dismissed addition on failure.
    if (willSoftDelete && setDismissedItems) {
      setDismissedItems((prev) => prev.filter((s) => s.id !== item.id));
    }
    reportError(toUserMessage(e, "Failed to delete strategy. Please try again."));
  } finally {
    refetchStrategies();
  }
}
