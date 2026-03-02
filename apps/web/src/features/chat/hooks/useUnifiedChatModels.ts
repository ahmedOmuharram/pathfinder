"use client";

/**
 * Manages the model catalog, model selection, and reasoning effort
 * for the unified chat panel.
 */

import { type Dispatch, type SetStateAction, useEffect, useState } from "react";
import { listModels } from "@/lib/api/client";
import { useSettingsStore } from "@/state/useSettingsStore";
import { buildModelSelection } from "@/features/chat/components/MessageComposer";
import type { ReasoningEffort, ModelCatalogEntry } from "@pathfinder/shared";

export interface UnifiedChatModels {
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

  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [reasoningEffort, setReasoningEffort] = useState<ReasoningEffort>("medium");

  // Sync from settings store defaults on mount / when defaults change
  useEffect(() => {
    setSelectedModelId(defaultModelId);
  }, [defaultModelId]);
  useEffect(() => {
    setReasoningEffort(defaultReasoningEffort);
  }, [defaultReasoningEffort]);

  // Fetch model catalog on mount
  useEffect(() => {
    listModels()
      .then((res) => setModelCatalog(res.models, res.default))
      .catch((err) => console.warn("[UnifiedChat] Failed to load models:", err));
  }, [setModelCatalog]);

  const currentModelSelection = buildModelSelection(
    selectedModelId,
    reasoningEffort,
    modelCatalog,
  );

  return {
    modelCatalog,
    catalogDefault,
    selectedModelId,
    setSelectedModelId,
    reasoningEffort,
    setReasoningEffort,
    currentModelSelection,
  };
}
