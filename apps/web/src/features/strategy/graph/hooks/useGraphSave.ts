import { useCallback, useState } from "react";
import { normalizePlan, updateStrategy } from "@/lib/api/strategies";
import { APIError } from "@/lib/api/http";
import { toUserMessage } from "@/lib/api/errors";
import type { StrategyPlan, Step, Strategy } from "@pathfinder/shared";
import { DEFAULT_STREAM_NAME } from "@pathfinder/shared";
import type { CombineMismatchGroup } from "@/lib/strategyGraph";
const isUuid = (value: string) =>
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value,
  );

interface UseGraphSaveArgs {
  strategy: Strategy | null;
  draftStrategy: Strategy | null;
  buildPlan: () => {
    plan: StrategyPlan;
    name: string;
    recordType: string | null;
  } | null;
  combineMismatchGroups: CombineMismatchGroup[];
  onToast?: (toast: {
    type: "success" | "error" | "warning" | "info";
    message: string;
  }) => void;
  setStrategyMeta: (meta: Partial<Strategy>) => void;
  buildStepSignature: (step: Step) => string;
  setLastSavedSteps: React.Dispatch<React.SetStateAction<Map<string, string>>>;
  setLastSavedStepsVersion: React.Dispatch<React.SetStateAction<number>>;
  validateSearchSteps: () => Promise<boolean>;
  nameValue: string;
  setNameValue: React.Dispatch<React.SetStateAction<string>>;
  descriptionValue: string;
}

type PersistPlanArgs = {
  overrideName?: string;
  overrideDescription?: string;
  toastOnSuccess?: boolean;
  toastOnWarnings?: boolean;
};

export function useGraphSave({
  strategy,
  draftStrategy,
  buildPlan,
  combineMismatchGroups,
  onToast,
  setStrategyMeta,
  buildStepSignature,
  setLastSavedSteps,
  setLastSavedStepsVersion,
  validateSearchSteps,
  nameValue,
  setNameValue,
  descriptionValue,
}: UseGraphSaveArgs) {
  const [isSaving, setIsSaving] = useState(false);

  const persistPlan = useCallback(
    async (args: PersistPlanArgs = {}) => {
      if (draftStrategy?.id == null || draftStrategy.id === "") return;
      const {
        overrideName,
        overrideDescription,
        toastOnSuccess = true,
        toastOnWarnings = true,
      } = args;

      if (!isUuid(draftStrategy.id)) {
        const message =
          "This draft isn't linked to a saved strategy yet. Open or create a strategy first, then save.";
        console.warn("Refusing to save: strategy id is not a UUID", {
          id: draftStrategy.id,
        });
        onToast?.({ type: "error", message });
        return;
      }
      if (combineMismatchGroups.length > 0) {
        const message =
          "Cannot save: the graph has validation issues (cannot combine steps with different record types).";
        if (toastOnWarnings) {
          onToast?.({ type: "error", message });
        }
        return;
      }
      if (
        (overrideName != null && overrideName !== "") ||
        overrideDescription !== undefined
      ) {
        const meta: Partial<Strategy> = {};
        meta.name = overrideName ?? draftStrategy.name;
        const metaDesc = overrideDescription ?? draftStrategy.description;
        if (metaDesc != null) {
          meta.description = metaDesc;
        }
        setStrategyMeta(meta);
      }
      const result = buildPlan();
      if (!result) {
        const message =
          "Cannot save: strategy must have a single final output step. Add a final combine step (e.g., UNION) to produce one output.";
        onToast?.({ type: "error", message });
        return;
      }
      let nextPlan = { ...result.plan };
      const nextName = overrideName ?? result.name;
      const nextDescription = overrideDescription ?? draftStrategy.description ?? null;
      nextPlan.metadata = {
        ...nextPlan.metadata,
        name: nextName,
      };
      if (nextDescription != null) {
        nextPlan.metadata.description = nextDescription;
      }
      setIsSaving(true);
      try {
        const normalized = await normalizePlan(draftStrategy.siteId, nextPlan);
        nextPlan = normalized.plan;
        const updated = await updateStrategy(draftStrategy.id, {
          name: nextName,
          plan: nextPlan,
        });
        const saveMeta: Partial<Strategy> = {
          name: updated.name,
          siteId: updated.siteId,
        };
        if (updated.recordType != null) {
          saveMeta.recordType = updated.recordType;
        }
        if (updated.description != null) {
          saveMeta.description = updated.description;
        }
        setStrategyMeta(saveMeta);
        if (draftStrategy.steps.length > 0) {
          const nextSavedSteps = new Map(
            draftStrategy.steps.map((step) => [step.id, buildStepSignature(step)]),
          );
          setLastSavedSteps(nextSavedSteps);
          setLastSavedStepsVersion((version) => version + 1);
        }
        if (toastOnSuccess) {
          onToast?.({ type: "success", message: "Strategy saved." });
        }
      } catch (error) {
        if (error instanceof APIError) {
          console.error("Failed to save strategy (API error)", {
            status: error.status,
            statusText: error.statusText,
            data: error.data,
          });
        } else {
          console.error("Failed to save strategy", error);
        }
        const message = toUserMessage(error, "Failed to save strategy.");
        onToast?.({ type: "error", message });
      } finally {
        setIsSaving(false);
      }
    },
    [
      draftStrategy,
      combineMismatchGroups.length,
      setStrategyMeta,
      buildPlan,
      setLastSavedSteps,
      setLastSavedStepsVersion,
      buildStepSignature,
      onToast,
    ],
  );

  const persistStrategyDetails = useCallback(
    async (name: string, description: string) => {
      if (draftStrategy?.id == null || draftStrategy.id === "") return;
      if (!buildPlan()) {
        const message =
          "Cannot save: strategy must have a single final output step. Add a final combine step (e.g., UNION) to produce one output.";
        onToast?.({ type: "error", message });
        return;
      }
      await persistPlan({ overrideName: name, overrideDescription: description });
    },
    [buildPlan, draftStrategy?.id, onToast, persistPlan],
  );

  const handleSave = useCallback(async () => {
    const name = nameValue.trim();
    if (name === "") {
      setNameValue(draftStrategy?.name ?? DEFAULT_STREAM_NAME);
      return;
    }
    const isValid = await validateSearchSteps();
    if (!isValid) {
      const message =
        "Cannot save: fix the validation errors highlighted in the graph first.";
      onToast?.({ type: "error", message });
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

  const canSave =
    draftStrategy != null && strategy?.id === draftStrategy.id && buildPlan() != null;

  return {
    isSaving,
    canSave,
    handleSave,
    persistPlan,
  };
}
