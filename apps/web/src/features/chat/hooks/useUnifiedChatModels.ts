"use client";

/**
 * Manages the model catalog, model selection, and reasoning effort
 * for the unified chat panel.
 */

import { useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { listModels } from "@/lib/api/models";
import { useSettingsStore } from "@/state/useSettingsStore";
import { buildModelSelection } from "@/features/chat/components/MessageComposer";
import type { ReasoningEffort, ModelCatalogEntry } from "@pathfinder/shared";

interface UnifiedChatModels {
  modelCatalog: ModelCatalogEntry[];
  catalogDefault: string | null;
  selectedModelId: string | null;
  setSelectedModelId: Dispatch<SetStateAction<string | null>>;
  reasoningEffort: ReasoningEffort;
  setReasoningEffort: Dispatch<SetStateAction<ReasoningEffort>>;
  currentModelSelection: ReturnType<typeof buildModelSelection>;
}

export function useUnifiedChatModels(): UnifiedChatModels {
  const modelCatalog = useSettingsStore((s) => s.modelCatalog);
  const setModelCatalog = useSettingsStore((s) => s.setModelCatalog);
  const catalogDefault = useSettingsStore((s) => s.catalogDefault);
  const defaultModelId = useSettingsStore((s) => s.defaultModelId);
  const defaultReasoningEffort = useSettingsStore((s) => s.defaultReasoningEffort);
  const modelOverrides = useSettingsStore((s) => s.modelOverrides);

  // Local overrides — null means "use store default"
  const [localModelId, setLocalModelId] = useState<string | null>(null);
  const [localEffort, setLocalEffort] = useState<ReasoningEffort | null>(null);

  // Effective values: local override wins, then store default
  const selectedModelId = localModelId ?? defaultModelId;
  const reasoningEffort = localEffort ?? defaultReasoningEffort;

  // Fetch model catalog once on mount
  useEffect(() => {
    listModels()
      .then((res) => setModelCatalog(res.models, res.default))
      .catch((err) => console.warn("[UnifiedChat] Failed to load models:", err));
  }, [setModelCatalog]);

  const currentModelSelection = buildModelSelection(
    selectedModelId,
    reasoningEffort,
    modelCatalog,
    selectedModelId ? modelOverrides[selectedModelId] : undefined,
  );

  return {
    modelCatalog,
    catalogDefault,
    selectedModelId,
    setSelectedModelId: setLocalModelId,
    reasoningEffort,
    setReasoningEffort: setLocalEffort as Dispatch<SetStateAction<ReasoningEffort>>,
    currentModelSelection,
  };
}
