/**
 * Plan state store — manages the active strategy plan and related UI state.
 */

import { createStore } from "./middleware";
import { useSessionStore } from "./useSessionStore";

import type { InteractivePlan } from "@/lib/types/plan";

type SendMessageFn = (text: string, metadata?: Record<string, unknown>) => void;

export type PipelinePhase =
  | "discovery"
  | "planning"
  | "execution"
  | "verification"
  | "completed";

export type PhaseStatus = "started" | "completed" | "failed" | "awaiting_approval";

interface PlanState {
  activePlan: InteractivePlan | null;
  isPlanPinned: boolean;
  planThoughts: string[];
  sendMessage: SendMessageFn | null;
  currentPhase: PipelinePhase | null;
  phaseStatus: PhaseStatus | null;

  setPlan: (plan: InteractivePlan) => void;
  updatePlan: (updates: Partial<InteractivePlan>) => void;
  clearPlan: () => void;
  setPinned: (pinned: boolean) => void;
  addThought: (thought: string) => void;
  clearThoughts: () => void;
  registerSendMessage: (fn: SendMessageFn) => void;
  setPhase: (phase: PipelinePhase, status: PhaseStatus) => void;
  clearPhase: () => void;
}

export const usePlanStore = createStore<PlanState>("PlanStore", (set) => ({
  activePlan: null,
  isPlanPinned: false,
  planThoughts: [],
  sendMessage: null,
  currentPhase: null,
  phaseStatus: null,

  setPlan: (plan) => set({ activePlan: plan }),
  updatePlan: (updates) =>
    set((state) => ({
      activePlan: state.activePlan ? { ...state.activePlan, ...updates } : null,
    })),
  clearPlan: () => set({ activePlan: null, isPlanPinned: false }),
  setPinned: (pinned) => set({ isPlanPinned: pinned }),
  addThought: (thought) =>
    set((state) => ({ planThoughts: [...state.planThoughts, thought] })),
  clearThoughts: () => set({ planThoughts: [] }),
  registerSendMessage: (fn) => set({ sendMessage: fn }),
  setPhase: (phase, status) => set({ currentPhase: phase, phaseStatus: status }),
  clearPhase: () => set({ currentPhase: null, phaseStatus: null }),
}));

useSessionStore.subscribe(
  (s) => s.strategyId,
  (current, previous) => {
    if (previous != null && previous !== "" && current !== previous) {
      usePlanStore.getState().clearPlan();
      usePlanStore.getState().clearThoughts();
    }
  },
);
