"use client";

import type {
  ModelProvider,
  PipelinePhase,
  ReasoningEffort,
  TierName,
} from "@pathfinder/shared";
import type { PipelineConfigPayload } from "@pathfinder/shared/generated/types/PipelineConfigPayload";
import { useSuspenseQueries } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import {
  DEFAULT_PIPELINE_CONFIG,
  useUpdateUserPreferences,
  userPreferencesOptions,
} from "@/lib/api/me";
import { modelCatalogOptions } from "@/lib/api/models";
import { tierPresetsOptions } from "@/lib/api/tiers";
import { QueryBoundary } from "@/lib/components/QueryBoundary";
import { Button } from "@/lib/components/ui/Button";

import { CatalogPanel } from "./CatalogPanel";
import { PipelinePanel } from "./PipelinePanel";

interface EngineModalProps {
  open: boolean;
  onClose: () => void;
}

export function EngineModal({ open, onClose }: EngineModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="flex h-[90vh] w-[90vw] max-w-7xl flex-col rounded-xl border bg-background shadow-2xl">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h2 className="text-lg font-semibold">AI Engine</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <QueryBoundary>
          <EngineModalContent />
        </QueryBoundary>

        <div className="flex justify-end gap-2 border-t px-6 py-3">
          <Button onClick={onClose}>Done</Button>
        </div>
      </div>
    </div>
  );
}

function EngineModalContent() {
  const [
    { data: catalog },
    { data: tiers },
    { data: prefs },
  ] = useSuspenseQueries({
    queries: [
      modelCatalogOptions(),
      tierPresetsOptions(),
      userPreferencesOptions(),
    ],
  });
  const update = useUpdateUserPreferences();

  const models = catalog.models;
  const config: PipelineConfigPayload =
    prefs.pipelineConfig ?? DEFAULT_PIPELINE_CONFIG;

  const [selectedPhase, setSelectedPhase] = useState<PipelinePhase | null>(null);

  const writeConfig = (next: PipelineConfigPayload): void => {
    update.mutate(
      { pipelineConfig: next },
      {
        onError: (err) => {
          toast.error(
            err instanceof Error
              ? err.message
              : "Failed to save AI engine preferences",
          );
        },
      },
    );
  };

  const handleProviderChange = (provider: ModelProvider) => {
    const preset = tiers.presets[provider]?.["balanced"];
    const next: PipelineConfigPayload = preset
      ? { provider, tier: "balanced", phases: preset }
      : { ...config, provider };
    writeConfig(next);
    setSelectedPhase(null);
  };

  const handleTierChange = (tier: TierName) => {
    const preset = tiers.presets[config.provider]?.[tier];
    if (!preset) return;
    writeConfig({ provider: config.provider, tier, phases: preset });
    setSelectedPhase(null);
  };

  const handleSelectModel = (modelId: string) => {
    if (!selectedPhase) return;
    const existing = config.phases[selectedPhase] ?? {
      modelId,
      reasoningEffort: "medium" as ReasoningEffort,
    };
    writeConfig({
      ...config,
      tier: "custom",
      phases: {
        ...config.phases,
        [selectedPhase]: { ...existing, modelId },
      },
    });
  };

  const handleEffortChange = (phase: PipelinePhase, effort: ReasoningEffort) => {
    const existing = config.phases[phase];
    if (!existing) return;
    writeConfig({
      ...config,
      tier: "custom",
      phases: {
        ...config.phases,
        [phase]: { ...existing, reasoningEffort: effort },
      },
    });
  };

  const activeModelId = selectedPhase
    ? config.phases[selectedPhase]?.modelId ?? null
    : null;

  return (
    <div className="flex flex-1 overflow-hidden">
      <div className="w-[35%] overflow-y-auto border-r">
        <PipelinePanel
          models={models}
          config={config}
          selectedPhase={selectedPhase}
          onSelectPhase={setSelectedPhase}
          onProviderChange={handleProviderChange}
          onTierChange={handleTierChange}
          onEffortChange={handleEffortChange}
        />
      </div>
      <div className="flex-1 overflow-hidden">
        <CatalogPanel
          models={models}
          selectedPhase={selectedPhase}
          activeModelId={activeModelId}
          onSelectModel={handleSelectModel}
        />
      </div>
    </div>
  );
}
