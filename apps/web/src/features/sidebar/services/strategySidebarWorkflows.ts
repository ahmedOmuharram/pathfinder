import type { Strategy } from "@pathfinder/shared";
import { toUserMessage } from "@/lib/api/errors";

export async function runDeleteStrategyWorkflow(args: {
  item: Strategy;
  currentStrategyId: string | null;
  setStrategyItems: (updater: (prev: Strategy[]) => Strategy[]) => void;
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
    clearStrategy,
    removeStrategy,
    setStrategyId,
    setDeleteError,
    deleteStrategyApi,
    deleteFromWdk,
    refetchStrategies,
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
    await deleteStrategyApi(item.id, deleteFromWdk);
  } catch (e) {
    reportError(toUserMessage(e, "Failed to delete strategy. Please try again."));
  } finally {
    refetchStrategies();
  }
}
