import { useEffect } from "react";
import type { StrategyStep, StrategyWithMeta } from "@/types/strategy";
import type { MutableRef } from "@/shared/types/refs";

export function useSavedSnapshotSync(args: {
  strategy: StrategyWithMeta | null;
  planHash: string | null;
  lastSnapshotIdRef: MutableRef<string | null>;
  setLastSavedPlanHash: (value: string | null) => void;
  lastSavedStepsRef: MutableRef<Map<string, string>>;
  buildStepSignature: (step: StrategyStep) => string;
  bumpLastSavedStepsVersion: () => void;
}) {
  const {
    strategy,
    planHash,
    lastSnapshotIdRef,
    setLastSavedPlanHash,
    lastSavedStepsRef,
    buildStepSignature,
    bumpLastSavedStepsVersion,
  } = args;

  useEffect(() => {
    const snapshotId = strategy?.id || null;
    if (!snapshotId || snapshotId === lastSnapshotIdRef.current) return;
    if (!planHash) return;
    lastSnapshotIdRef.current = snapshotId;
    setLastSavedPlanHash(planHash);
    if (strategy?.steps) {
      lastSavedStepsRef.current = new Map(
        strategy.steps.map((step) => [step.id, buildStepSignature(step)])
      );
      bumpLastSavedStepsVersion();
    }
  }, [
    strategy?.id,
    strategy?.steps,
    planHash,
    buildStepSignature,
    lastSnapshotIdRef,
    setLastSavedPlanHash,
    lastSavedStepsRef,
    bumpLastSavedStepsVersion,
  ]);
}

