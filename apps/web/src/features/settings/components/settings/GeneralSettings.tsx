"use client";

/**
 * GeneralSettings -- default model and reasoning effort settings.
 */

import { useSettingsStore } from "@/state/useSettingsStore";
import { ModelPicker } from "@/features/chat/components/thinking/ModelPicker";
import { ReasoningToggle } from "@/features/chat/components/message/ReasoningToggle";
import { SettingsField } from "./SettingsField";

export function GeneralSettings() {
  const modelCatalog = useSettingsStore((s) => s.modelCatalog);
  const catalogDefault = useSettingsStore((s) => s.catalogDefault);
  const defaultModelId = useSettingsStore((s) => s.defaultModelId);
  const setDefaultModelId = useSettingsStore((s) => s.setDefaultModelId);
  const defaultReasoningEffort = useSettingsStore((s) => s.defaultReasoningEffort);
  const setDefaultReasoningEffort = useSettingsStore(
    (s) => s.setDefaultReasoningEffort,
  );

  const selectedModel = modelCatalog.find((m) => m.id === defaultModelId);
  const supportsReasoning = selectedModel?.supportsReasoning ?? false;

  const serverDefaultId = catalogDefault;

  return (
    <div className="space-y-5">
      <SettingsField label="Default model">
        <ModelPicker
          models={modelCatalog}
          selectedModelId={defaultModelId}
          onSelect={(id) => setDefaultModelId(id || null)}
          serverDefaultId={serverDefaultId}
        />
        <p className="mt-1 text-xs text-muted-foreground">
          Used when no per-request model is chosen.
        </p>
      </SettingsField>

      <SettingsField label="Default reasoning effort">
        {supportsReasoning || !defaultModelId ? (
          <>
            <ReasoningToggle
              value={defaultReasoningEffort}
              onChange={setDefaultReasoningEffort}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              {defaultModelId
                ? "Applied when the selected model supports reasoning."
                : "Applied to all reasoning-capable models."}
            </p>
          </>
        ) : (
          <p className="text-xs text-muted-foreground">
            Selected model does not support reasoning.
          </p>
        )}
      </SettingsField>
    </div>
  );
}
