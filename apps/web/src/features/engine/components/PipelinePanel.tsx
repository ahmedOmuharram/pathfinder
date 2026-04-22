"use client";

import type {
  ModelCatalogEntry,
  ModelProvider,
  PipelinePhase,
  ReasoningEffort,
  TierName,
} from "@pathfinder/shared";
import type { PipelineConfigPayload } from "@pathfinder/shared/generated/types/PipelineConfigPayload";
import { ChevronDown } from "lucide-react";

import { OrchestratorSelect } from "./OrchestratorSelect";
import { PhaseCard } from "./PhaseCard";

const PHASES: PipelinePhase[] = [
  "scoping",
  "discovery",
  "planning",
  "execution",
  "verification",
];
const PHASE_TRANSITIONS: Record<string, string> = {
  "scoping→discovery": "Problem frame",
  "discovery→planning": "Findings",
  "planning→execution": "Plan",
  "execution→verification": "Strategy",
};
const TIER_OPTIONS: { value: TierName; label: string }[] = [
  { value: "quality", label: "Quality" },
  { value: "balanced", label: "Balanced" },
  { value: "fast", label: "Fast" },
];
const PROVIDER_OPTIONS: { value: ModelProvider; label: string }[] = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "google", label: "Google" },
  { value: "ollama", label: "Ollama" },
];

interface PipelinePanelProps {
  models: ModelCatalogEntry[];
  config: PipelineConfigPayload;
  selectedPhase: PipelinePhase | null;
  onSelectPhase: (phase: PipelinePhase) => void;
  onProviderChange: (provider: ModelProvider) => void;
  onTierChange: (tier: TierName) => void;
  onEffortChange: (phase: PipelinePhase, effort: ReasoningEffort) => void;
}

export function PipelinePanel({
  models,
  config,
  selectedPhase,
  onSelectPhase,
  onProviderChange,
  onTierChange,
  onEffortChange,
}: PipelinePanelProps) {
  const { provider, tier, phases } = config;
  const isOllama = provider === "ollama";

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div>
        <label className="mb-1 block text-xs font-medium text-muted-foreground">
          Provider
        </label>
        <select
          value={provider}
          onChange={(e) => onProviderChange(e.target.value as ModelProvider)}
          className="w-full rounded-md border bg-background px-3 py-2 text-sm"
        >
          {PROVIDER_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-muted-foreground">
          Tier
        </label>
        <select
          value={tier}
          onChange={(e) => onTierChange(e.target.value as TierName)}
          disabled={isOllama}
          className="w-full rounded-md border bg-background px-3 py-2 text-sm disabled:opacity-50"
        >
          {TIER_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
          {tier === "custom" && <option value="custom">Custom</option>}
        </select>
      </div>

      <div className="h-px bg-border" />

      <OrchestratorSelect models={models} />

      <div className="h-px bg-border" />

      <div className="flex flex-1 flex-col gap-1">
        <span className="text-xs font-medium text-muted-foreground">Pipeline</span>
        {PHASES.map((phase, i) => {
          const phaseConfig = phases[phase];
          if (!phaseConfig) return null;
          return (
            <div key={phase}>
              <PhaseCard
                phase={phase}
                config={phaseConfig}
                models={models}
                isSelected={selectedPhase === phase}
                onSelect={() => onSelectPhase(phase)}
                onEffortChange={(effort) => onEffortChange(phase, effort)}
              />
              {i < PHASES.length - 1 && (
                <div className="flex items-center justify-center gap-1.5 py-0.5">
                  <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-[10px] text-muted-foreground">
                    {PHASE_TRANSITIONS[`${PHASES[i]}→${PHASES[i + 1]}`]}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
