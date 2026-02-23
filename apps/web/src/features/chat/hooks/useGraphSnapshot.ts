import { useCallback } from "react";
import type { StrategyStep, StrategyWithMeta } from "@/features/strategy/types";
import type { GraphSnapshotInput } from "@/features/chat/utils/graphSnapshot";
import { buildStrategyFromGraphSnapshot } from "@/features/chat/utils/graphSnapshot";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";

interface UseGraphSnapshotArgs {
  siteId: string;
  strategyId: string | null;
  stepsById: Record<string, StrategyStep>;
  sessionRef: { current: StreamingSession | null };
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
  sessionRef,
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
      const session = sessionRef.current;
      session?.captureUndoSnapshot(snapshotId);
      const nextStrategy = buildStrategyFromGraphSnapshot({
        snapshotId,
        siteId,
        graphSnapshot,
        stepsById,
        existingStrategy: session?.latestStrategy ?? null,
      });
      setStrategy(nextStrategy);
      setStrategyMeta({
        name: nextStrategy.name,
        description: nextStrategy.description,
        recordType: nextStrategy.recordType ?? undefined,
      });
      session?.markSnapshotApplied();
    },
    [strategyId, sessionRef, siteId, stepsById, setStrategy, setStrategyMeta],
  );

  return { applyGraphSnapshot };
}
