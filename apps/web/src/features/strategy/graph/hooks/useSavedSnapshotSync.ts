import { useEffect } from "react";
import type { StrategyStep, StrategyWithMeta } from "@/features/strategy/types";
import { usePrevious } from "@/lib/hooks/usePrevious";

export function useSavedSnapshotSync(args: {
  strategy: StrategyWithMeta | null;
  planHash: string | null;
  setLastSavedPlanHash: (value: string | null) => void;
  setLastSavedSteps: (value: Map<string, string>) => void;
  buildStepSignature: (step: StrategyStep) => string;
  bumpLastSavedStepsVersion: () => void;
}) {
  const {
    strategy,
    planHash,
    setLastSavedPlanHash,
    setLastSavedSteps,
    buildStepSignature,
    bumpLastSavedStepsVersion,
  } = args;

  const snapshotId = strategy?.id || null;
  const prevSnapshotId = usePrevious(snapshotId);

  useEffect(() => {
    if (!snapshotId || snapshotId === prevSnapshotId) return;
    if (!planHash) return;
    setLastSavedPlanHash(planHash);
    if (strategy?.steps) {
      setLastSavedSteps(
        new Map(strategy.steps.map((step) => [step.id, buildStepSignature(step)])),
      );
      bumpLastSavedStepsVersion();
    }
  }, [
    snapshotId,
    prevSnapshotId,
    strategy?.steps,
    planHash,
    buildStepSignature,
    setLastSavedPlanHash,
    setLastSavedSteps,
    bumpLastSavedStepsVersion,
  ]);
}
