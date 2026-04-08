import type { Step, Strategy } from "@pathfinder/shared";
import type { GraphSnapshotInput } from "@/features/chat/utils/graphSnapshot";
import { buildStrategyFromGraphSnapshot } from "@/features/chat/utils/graphSnapshot";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import { useStrategyStore } from "@/state/strategy/store";

interface UseGraphSnapshotArgs {
  siteId: string;
  strategyId: string | null;
  stepsById: Record<string, Step>;
  sessionRef: { current: StreamingSession | null };
  setStrategy: (strategy: Strategy) => void;
  setStrategyMeta: (meta: {
    name?: string;
    description?: string | null;
    recordType?: string | null;
  }) => void;
}

export function useGraphSnapshot({
  siteId,
  strategyId,
  stepsById,
  sessionRef,
  setStrategy,
  setStrategyMeta,
}: UseGraphSnapshotArgs) {
  const applyGraphSnapshot = (graphSnapshot: GraphSnapshotInput) => {
    const snapshotId =
      (graphSnapshot.graphId != null && graphSnapshot.graphId !== ""
        ? graphSnapshot.graphId
        : null) ??
      strategyId ??
      null;
    if (snapshotId == null || snapshotId === "") return;
    if (strategyId != null && strategyId !== "" && snapshotId !== strategyId) {
      return;
    }
    const session = sessionRef.current;
    const currentStrategy = useStrategyStore.getState().strategy;
    session?.captureUndoSnapshot(snapshotId, currentStrategy);
    const nextStrategy = buildStrategyFromGraphSnapshot({
      snapshotId,
      siteId,
      graphSnapshot,
      stepsById,
      existingStrategy: currentStrategy,
    });
    setStrategy(nextStrategy);
    setStrategyMeta({
      name: nextStrategy.name,
      ...(nextStrategy.description != null
        ? { description: nextStrategy.description }
        : {}),
      ...(nextStrategy.recordType != null
        ? { recordType: nextStrategy.recordType }
        : {}),
    });
    session?.markSnapshotApplied();
  };

  return { applyGraphSnapshot };
}
