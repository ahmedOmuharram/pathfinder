import { useCallback } from "react";
import type { StrategyStep, StrategyWithMeta } from "@/types/strategy";
import type { GraphSnapshotInput } from "@/features/chat/utils/graphSnapshot";
import { buildStrategyFromGraphSnapshot } from "@/features/chat/utils/graphSnapshot";
import type { MutableRef } from "@/shared/types/refs";

interface UseGraphSnapshotArgs {
  siteId: string;
  strategyId: string | null;
  stepsById: Record<string, StrategyStep>;
  strategyRef: MutableRef<StrategyWithMeta | null>;
  pendingUndoSnapshotRef: MutableRef<StrategyWithMeta | null>;
  appliedSnapshotRef: MutableRef<boolean>;
  setStrategy: (strategy: StrategyWithMeta) => void;
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
  strategyRef,
  pendingUndoSnapshotRef,
  appliedSnapshotRef,
  setStrategy,
  setStrategyMeta,
}: UseGraphSnapshotArgs) {
  const applyGraphSnapshot = useCallback(
    (graphSnapshot: GraphSnapshotInput) => {
      if (!graphSnapshot) return;
      const snapshotId = graphSnapshot.graphId || strategyId || null;
      if (!snapshotId) return;
      if (strategyId && snapshotId !== strategyId) {
        return;
      }
      const snapshot = strategyRef.current;
      if (
        !pendingUndoSnapshotRef.current &&
        snapshot &&
        snapshot.id === snapshotId
      ) {
        pendingUndoSnapshotRef.current = snapshot;
      }
      const nextStrategy = buildStrategyFromGraphSnapshot({
        snapshotId,
        siteId,
        graphSnapshot,
        stepsById,
        existingStrategy: snapshot,
      });
      setStrategy(nextStrategy);
      setStrategyMeta({
        name: nextStrategy.name,
        description: nextStrategy.description,
        recordType: nextStrategy.recordType ?? undefined,
      });
      appliedSnapshotRef.current = true;
    },
    [
      strategyId,
      strategyRef,
      pendingUndoSnapshotRef,
      siteId,
      stepsById,
      setStrategy,
      setStrategyMeta,
      appliedSnapshotRef,
    ]
  );

  return { applyGraphSnapshot };
}
