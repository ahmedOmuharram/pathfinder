import { create } from "zustand";

import type { DataSubAgentStepPayload } from "@pathfinder/shared";

interface SubAgentStepsState {
  /** Inner steps grouped by the Lead's tool_call_id for each sub-agent dispatch. */
  byParent: Record<string, DataSubAgentStepPayload[]>;
  appendStep: (step: DataSubAgentStepPayload) => void;
  reset: () => void;
}

export const useSubAgentStepsStore = create<SubAgentStepsState>((set) => ({
  byParent: {},
  appendStep: (step) =>
    set((s) => {
      const existing = s.byParent[step.parentToolCallId] ?? [];
      return {
        byParent: {
          ...s.byParent,
          [step.parentToolCallId]: [...existing, step],
        },
      };
    }),
  reset: () => set({ byParent: {} }),
}));
