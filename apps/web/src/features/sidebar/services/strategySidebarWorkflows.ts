import type { StrategyListItem } from "@/features/sidebar/utils/strategyItems";
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
