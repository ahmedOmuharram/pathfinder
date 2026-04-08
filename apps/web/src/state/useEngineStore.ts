import { createPersistedStore } from "./middleware";
import type {
  ModelProvider,
  PipelineConfig,
  PipelinePhaseConfig,
  ReasoningEffort,
  TierName,
  PipelinePhase,
} from "@pathfinder/shared";

interface EngineState {
  provider: ModelProvider;
  tier: TierName;
  phases: PipelineConfig;

  // Actions
  setProvider: (provider: ModelProvider) => void;
  setTier: (tier: TierName, phases: PipelineConfig) => void;
  setPhaseConfig: (phase: PipelinePhase, config: PipelinePhaseConfig) => void;
  setPhaseModel: (phase: PipelinePhase, modelId: string) => void;
  setPhaseEffort: (phase: PipelinePhase, effort: ReasoningEffort) => void;
  applyPreset: (provider: ModelProvider, tier: TierName, phases: PipelineConfig) => void;
  getPipelinePayload: () => PipelineConfig;
}

const DEFAULT_PHASES: PipelineConfig = {
  discovery: { modelId: "anthropic/claude-sonnet-4-6", reasoningEffort: "medium" },
  planning: { modelId: "anthropic/claude-opus-4-6", reasoningEffort: "high" },
  execution: { modelId: "anthropic/claude-sonnet-4-6", reasoningEffort: "medium" },
  verification: { modelId: "anthropic/claude-opus-4-6", reasoningEffort: "high" },
};

export const useEngineStore = createPersistedStore<EngineState>(
  "EngineStore",
  (set, get) => ({
    provider: "anthropic",
    tier: "balanced" as TierName,
    phases: DEFAULT_PHASES,

    setProvider: (provider) => set({ provider }),

    setTier: (tier, phases) => set({ tier, phases }),

    setPhaseConfig: (phase, config) =>
      set((state) => ({
        tier: "custom" as TierName,
        phases: { ...state.phases, [phase]: config },
      })),

    setPhaseModel: (phase, modelId) =>
      set((state) => ({
        tier: "custom" as TierName,
        phases: {
          ...state.phases,
          [phase]: { ...state.phases[phase], modelId },
        },
      })),

    setPhaseEffort: (phase, effort) =>
      set((state) => ({
        tier: "custom" as TierName,
        phases: {
          ...state.phases,
          [phase]: { ...state.phases[phase], reasoningEffort: effort },
        },
      })),

    applyPreset: (provider, tier, phases) =>
      set({ provider, tier, phases }),

    getPipelinePayload: () => get().phases,
  }),
  {
    name: "pathfinder-engine",
    partialize: (s) => ({
      provider: s.provider,
      tier: s.tier,
      phases: s.phases,
    }),
  },
);
