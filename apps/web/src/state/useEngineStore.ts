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

export const DEFAULT_PHASES: PipelineConfig = {
  scoping: { modelId: "openai:gpt-4.1-mini", reasoningEffort: "medium" },
  discovery: { modelId: "openai:gpt-4.1-mini", reasoningEffort: "medium" },
  planning: { modelId: "openai:gpt-4.1-mini", reasoningEffort: "medium" },
  execution: { modelId: "openai:gpt-4.1-mini", reasoningEffort: "medium" },
  verification: { modelId: "openai:gpt-4.1-mini", reasoningEffort: "medium" },
};

export function normalizePipelineConfig(phases?: Partial<PipelineConfig> | null): PipelineConfig {
  return {
    scoping: phases?.scoping ?? DEFAULT_PHASES.scoping,
    discovery: phases?.discovery ?? DEFAULT_PHASES.discovery,
    planning: phases?.planning ?? DEFAULT_PHASES.planning,
    execution: phases?.execution ?? DEFAULT_PHASES.execution,
    verification: phases?.verification ?? DEFAULT_PHASES.verification,
  };
}

export const useEngineStore = createPersistedStore<EngineState>(
  "EngineStore",
  (set, get) => ({
    provider: "openai",
    tier: "fast" as TierName,
    phases: DEFAULT_PHASES,

    setProvider: (provider) => set({ provider }),

    setTier: (tier, phases) => set({ tier, phases: normalizePipelineConfig(phases) }),

    setPhaseConfig: (phase, config) =>
      set((state) => ({
        tier: "custom" as TierName,
        phases: { ...normalizePipelineConfig(state.phases), [phase]: config },
      })),

    setPhaseModel: (phase, modelId) =>
      set((state) => {
        const phases = normalizePipelineConfig(state.phases);
        return {
          tier: "custom" as TierName,
          phases: {
            ...phases,
            [phase]: { ...phases[phase], modelId },
          },
        };
      }),

    setPhaseEffort: (phase, effort) =>
      set((state) => {
        const phases = normalizePipelineConfig(state.phases);
        return {
          tier: "custom" as TierName,
          phases: {
            ...phases,
            [phase]: { ...phases[phase], reasoningEffort: effort },
          },
        };
      }),

    applyPreset: (provider, tier, phases) =>
      set({ provider, tier, phases: normalizePipelineConfig(phases) }),

    getPipelinePayload: () => normalizePipelineConfig(get().phases),
  }),
  {
    name: "pathfinder-engine",
    partialize: (s) => ({
      provider: s.provider,
      tier: s.tier,
      phases: normalizePipelineConfig(s.phases),
    }),
  },
);
