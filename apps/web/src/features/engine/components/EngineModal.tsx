import type { ModelProvider, PipelinePhase, TierName } from "@pathfinder/shared";
import { useSuspenseQueries } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useState } from "react";
import { useShallow } from "zustand/react/shallow";

import { modelCatalogOptions } from "@/lib/api/models";
import { tierPresetsOptions } from "@/lib/api/tiers";
import { QueryBoundary } from "@/lib/components/QueryBoundary";
import { Button } from "@/lib/components/ui/Button";
import { useEngineStore } from "@/state/useEngineStore";
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
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h2 className="text-lg font-semibold">AI Engine</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <QueryBoundary>
          <EngineModalContent />
        </QueryBoundary>

        {/* Footer */}
        <div className="flex justify-end gap-2 border-t px-6 py-3">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={onClose}>Apply</Button>
        </div>
      </div>
    </div>
  );
}

function EngineModalContent() {
  const [{ data: catalog }, { data: tiers }] = useSuspenseQueries({
    queries: [modelCatalogOptions(), tierPresetsOptions()],
  });
  const models = catalog.models;

  const { phases, setPhaseModel, applyPreset } = useEngineStore(
    useShallow((s) => ({
      phases: s.phases,
      setPhaseModel: s.setPhaseModel,
      applyPreset: s.applyPreset,
    })),
  );
  const [selectedPhase, setSelectedPhase] = useState<PipelinePhase | null>(null);

  const handleProviderChange = (provider: ModelProvider) => {
    const providerTiers = tiers.presets[provider];
    const balancedPreset = providerTiers?.["balanced"];
    if (balancedPreset) {
      applyPreset(provider, "balanced", balancedPreset);
    } else {
      useEngineStore.getState().setProvider(provider);
    }
    setSelectedPhase(null);
  };

  const handleTierChange = (tier: TierName) => {
    const provider = useEngineStore.getState().provider;
    const preset = tiers.presets[provider]?.[tier];
    if (preset) {
      applyPreset(provider, tier, preset);
    }
    setSelectedPhase(null);
  };

  const handleSelectModel = (modelId: string) => {
    if (selectedPhase) {
      setPhaseModel(selectedPhase, modelId);
    }
  };

  const activeModelId = selectedPhase ? phases[selectedPhase].modelId : null;

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Left panel */}
      <div className="w-[35%] overflow-y-auto border-r">
        <PipelinePanel
          models={models}
          selectedPhase={selectedPhase}
          onSelectPhase={setSelectedPhase}
          onProviderChange={handleProviderChange}
          onTierChange={handleTierChange}
        />
      </div>

      {/* Right panel */}
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
