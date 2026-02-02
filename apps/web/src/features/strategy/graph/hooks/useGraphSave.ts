import { useCallback, useState } from "react";
import { normalizePlan, updateStrategy } from "@/lib/api/client";
import type { StrategyPlan } from "@pathfinder/shared";
import type { StrategyStep, StrategyWithMeta } from "@/types/strategy";
import type { CombineMismatchGroup } from "@/features/strategy/domain/graph";
import type { MutableRef } from "@/shared/types/refs";

interface UseGraphSaveArgs {
  strategy: StrategyWithMeta | null;
  draftStrategy: StrategyWithMeta | null;
  buildPlan: () =>
    | { plan: StrategyPlan; name: string; recordType: string | null }
    | null;
  combineMismatchGroups: CombineMismatchGroup[];
  onToast?: (toast: { type: "success" | "error" | "warning" | "info"; message: string }) => void;
  onPush?: () => void;
  setStrategyMeta: (meta: Partial<StrategyWithMeta>) => void;
  buildStepSignature: (step: StrategyStep) => string;
  lastSavedStepsRef: MutableRef<Map<string, string>>;
  setLastSavedStepsVersion: React.Dispatch<React.SetStateAction<number>>;
  setLastSavedPlanHash: React.Dispatch<React.SetStateAction<string | null>>;
  validateSearchSteps: () => Promise<boolean>;
  nameValue: string;
  setNameValue: React.Dispatch<React.SetStateAction<string>>;
  descriptionValue: string;
}

export function useGraphSave({
  strategy,
  draftStrategy,
  buildPlan,
  combineMismatchGroups,
  onToast,
  onPush,
  setStrategyMeta,
  buildStepSignature,
  lastSavedStepsRef,
  setLastSavedStepsVersion,
  setLastSavedPlanHash,
  validateSearchSteps,
  nameValue,
  setNameValue,
  descriptionValue,
}: UseGraphSaveArgs) {
  const [isSaving, setIsSaving] = useState(false);
  const [, setSaveError] = useState<string | null>(null);

  const failCombineMismatch = useCallback(() => {
    const message = "Cannot combine steps with different record types.";
    setSaveError(message);
    onToast?.({ type: "error", message });
  }, [onToast]);

  const persistPlan = useCallback(
    async (overrideName?: string, overrideDescription?: string) => {
      if (!draftStrategy?.id) return;
      setSaveError(null);
      if (combineMismatchGroups.length > 0) {
        failCombineMismatch();
        return;
      }
      if (overrideName || overrideDescription !== undefined) {
        setStrategyMeta({
          name: overrideName ?? draftStrategy?.name ?? undefined,
          description: overrideDescription ?? draftStrategy?.description ?? undefined,
        });
      }
      const result = buildPlan();
      if (!result) return;
      let nextPlan = { ...result.plan };
      const nextMeta =
        typeof nextPlan.metadata === "object" && nextPlan.metadata !== null
          ? { ...(nextPlan.metadata as Record<string, unknown>) }
          : {};
      const nextName = overrideName || result.name;
      const nextDescription =
        overrideDescription !== undefined
          ? overrideDescription
          : (draftStrategy?.description ?? null);
      nextMeta.name = nextName;
      nextMeta.description = nextDescription;
      nextPlan.metadata = nextMeta;
      setIsSaving(true);
      try {
        const normalized = await normalizePlan(draftStrategy.siteId, nextPlan);
        nextPlan = normalized.plan;
        const updated = await updateStrategy(draftStrategy.id, {
          name: nextName,
          plan: nextPlan,
        });
        setStrategyMeta({
          name: updated.name,
          recordType: updated.recordType ?? undefined,
          siteId: updated.siteId,
          description: updated.description ?? undefined,
        });
        setLastSavedPlanHash(JSON.stringify(nextPlan));
        if (draftStrategy?.steps) {
          const nextSavedSteps = new Map(
            draftStrategy.steps.map((step) => [step.id, buildStepSignature(step)])
          );
          lastSavedStepsRef.current = nextSavedSteps;
          setLastSavedStepsVersion((version) => version + 1);
        }
        onToast?.({ type: "success", message: "Strategy saved." });
      } catch (error) {
        console.error("Failed to save strategy", error);
        setSaveError("Failed to save strategy.");
        onToast?.({ type: "error", message: "Failed to save strategy." });
      } finally {
        setIsSaving(false);
      }
    },
    [
      draftStrategy,
      combineMismatchGroups.length,
      failCombineMismatch,
      setStrategyMeta,
      buildPlan,
      setLastSavedPlanHash,
      lastSavedStepsRef,
      setLastSavedStepsVersion,
      buildStepSignature,
      onToast,
    ]
  );

  const persistStrategyDetails = useCallback(
    async (name: string, description: string) => {
      if (!buildPlan() || !draftStrategy?.id) return;
      await persistPlan(name, description);
    },
    [buildPlan, draftStrategy?.id, persistPlan]
  );

  const handleSave = useCallback(async () => {
    setSaveError(null);
    const name = nameValue.trim();
    if (!name) {
      setNameValue(draftStrategy?.name || "Draft Strategy");
      return;
    }
    const isValid = await validateSearchSteps();
    if (!isValid) {
      setSaveError("Fix validation errors before saving.");
      onToast?.({ type: "error", message: "Fix validation errors before saving." });
      return;
    }
    await persistStrategyDetails(name, descriptionValue.trim());
  }, [
    nameValue,
    setNameValue,
    draftStrategy?.name,
    validateSearchSteps,
    persistStrategyDetails,
    descriptionValue,
    onToast,
  ]);

  const handlePush = useCallback(async () => {
    if (!onPush) return;
    setSaveError(null);
    if (combineMismatchGroups.length > 0) {
      failCombineMismatch();
      return;
    }
    await onPush();
  }, [onPush, combineMismatchGroups.length, failCombineMismatch]);

  const canSave = !!draftStrategy && strategy?.id === draftStrategy.id && !!buildPlan();

  return {
    isSaving,
    canSave,
    handleSave,
    handlePush,
    persistPlan,
  };
}
