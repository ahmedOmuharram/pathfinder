/**
 * Plan state store — manages the active strategy plan and related UI state.
 */

import { createStore } from "./middleware";
import { useSessionStore } from "./useSessionStore";

import type { InteractivePlan } from "@/lib/types/plan";
import type { PlanActionRequest } from "@/lib/types/plan";
import type {
  GraphPlan,
  PhaseStatus as SharedPhaseStatus,
  PipelinePhase as SharedPipelinePhase,
  PlanArtifact,
  PlanUpdate,
} from "@pathfinder/shared";

type SendMessageFn = (text: string, metadata?: Record<string, unknown>) => void;
type SubmitPlanActionFn = (action: PlanActionRequest) => Promise<void>;

export type PhaseStatus = SharedPhaseStatus;
export type PipelinePhase = SharedPipelinePhase | "completed";
export type TimedPipelinePhase = SharedPipelinePhase;

export interface PhaseTiming {
  phase: TimedPipelinePhase;
  status: PhaseStatus;
  emittedAt: string | null;
  phaseStartedAt: string | null;
  phaseCompletedAt: string | null;
  durationMs: number | null;
}

export interface PendingPlanApproval {
  id: string;
  planId: string;
  toolCallId: string;
}

interface PlanState {
  activePlan: InteractivePlan | null;
  activePlanTraceId: string | null;
  activePlanMessageGroupId: string | null;
  isPlanPinned: boolean;
  planThoughts: string[];
  sendMessage: SendMessageFn | null;
  submitPlanAction: SubmitPlanActionFn | null;
  currentPhase: PipelinePhase | null;
  phaseStatus: PhaseStatus | null;
  phaseTimings: Partial<Record<TimedPipelinePhase, PhaseTiming>>;

  plans: PlanArtifact[];
  focusedPlanIndex: number;
  pendingApproval: PendingPlanApproval | null;
  planPreview: GraphPlan | null;
  lastPlanUpdate: PlanUpdate | null;

  setPlan: (plan: InteractivePlan) => void;
  setPlanTraceContext: (context: {
    traceId?: string | null;
    messageGroupId?: string | null;
  }) => void;
  updatePlan: (updates: Partial<InteractivePlan>) => void;
  clearPlan: () => void;
  setPinned: (pinned: boolean) => void;
  addThought: (thought: string) => void;
  clearThoughts: () => void;
  registerSendMessage: (fn: SendMessageFn) => void;
  registerPlanAction: (fn: SubmitPlanActionFn) => void;
  setPhase: (
    phase: PipelinePhase,
    status: PhaseStatus,
    timing?: Partial<Omit<PhaseTiming, "phase" | "status">>,
  ) => void;
  clearPhase: () => void;
  clearPhaseTimings: () => void;

  appendPlanArtifact: (artifact: PlanArtifact) => void;
  setFocusedPlanIndex: (index: number) => void;
  setPendingApproval: (approval: PendingPlanApproval | null) => void;
  resolvePendingApproval: () => void;
  setPlanPreview: (preview: GraphPlan) => void;
  applyPlanUpdate: (update: PlanUpdate) => void;
  recordPhaseChange: (
    phase: PipelinePhase,
    status: PhaseStatus,
    durationMs: number | null,
  ) => void;
}

export const usePlanStore = createStore<PlanState>("PlanStore", (set) => ({
  activePlan: null,
  activePlanTraceId: null,
  activePlanMessageGroupId: null,
  isPlanPinned: false,
  planThoughts: [],
  sendMessage: null,
  submitPlanAction: null,
  currentPhase: null,
  phaseStatus: null,
  phaseTimings: {},

  plans: [],
  focusedPlanIndex: 0,
  pendingApproval: null,
  planPreview: null,
  lastPlanUpdate: null,

  setPlan: (plan) => set({ activePlan: plan }),
  setPlanTraceContext: (context) =>
    set((state) => ({
      activePlanTraceId:
        "traceId" in context ? (context.traceId ?? null) : state.activePlanTraceId,
      activePlanMessageGroupId:
        "messageGroupId" in context
          ? (context.messageGroupId ?? null)
          : state.activePlanMessageGroupId,
    })),
  updatePlan: (updates) =>
    set((state) => ({
      activePlan: state.activePlan ? { ...state.activePlan, ...updates } : null,
    })),
  clearPlan: () =>
    set({
      activePlan: null,
      activePlanTraceId: null,
      activePlanMessageGroupId: null,
      isPlanPinned: false,
      currentPhase: null,
      phaseStatus: null,
      phaseTimings: {},
      plans: [],
      focusedPlanIndex: 0,
      pendingApproval: null,
      planPreview: null,
      lastPlanUpdate: null,
    }),
  setPinned: (pinned) => set({ isPlanPinned: pinned }),
  addThought: (thought) =>
    set((state) => ({ planThoughts: [...state.planThoughts, thought] })),
  clearThoughts: () => set({ planThoughts: [] }),
  registerSendMessage: (fn) => set({ sendMessage: fn }),
  registerPlanAction: (fn) => set({ submitPlanAction: fn }),
  setPhase: (phase, status, timing) =>
    set((state) => {
      const nextTimings = { ...state.phaseTimings };
      if (phase !== "completed") {
        nextTimings[phase] = {
          phase,
          status,
          emittedAt: timing?.emittedAt ?? nextTimings[phase]?.emittedAt ?? null,
          phaseStartedAt:
            timing?.phaseStartedAt ?? nextTimings[phase]?.phaseStartedAt ?? null,
          phaseCompletedAt:
            timing?.phaseCompletedAt ?? nextTimings[phase]?.phaseCompletedAt ?? null,
          durationMs: timing?.durationMs ?? nextTimings[phase]?.durationMs ?? null,
        };
      }
      return {
        currentPhase: phase,
        phaseStatus: status,
        phaseTimings: nextTimings,
      };
    }),
  clearPhase: () => set({ currentPhase: null, phaseStatus: null }),
  clearPhaseTimings: () => set({ phaseTimings: {} }),

  appendPlanArtifact: (artifact) =>
    set((state) => {
      const plans = [...state.plans, artifact];
      return { plans, focusedPlanIndex: plans.length - 1 };
    }),
  setFocusedPlanIndex: (index) =>
    set((state) => {
      if (state.plans.length === 0) return { focusedPlanIndex: 0 };
      const clamped = Math.max(0, Math.min(index, state.plans.length - 1));
      return { focusedPlanIndex: clamped };
    }),
  setPendingApproval: (approval) => set({ pendingApproval: approval }),
  resolvePendingApproval: () => set({ pendingApproval: null }),
  setPlanPreview: (preview) => set({ planPreview: preview }),
  applyPlanUpdate: (update) => set({ lastPlanUpdate: update }),
  recordPhaseChange: (phase, status, durationMs) =>
    set((state) => {
      const nextTimings = { ...state.phaseTimings };
      if (phase !== "completed") {
        nextTimings[phase] = {
          phase,
          status,
          emittedAt: nextTimings[phase]?.emittedAt ?? null,
          phaseStartedAt: nextTimings[phase]?.phaseStartedAt ?? null,
          phaseCompletedAt: nextTimings[phase]?.phaseCompletedAt ?? null,
          durationMs: durationMs ?? nextTimings[phase]?.durationMs ?? null,
        };
      }
      return {
        currentPhase: phase,
        phaseStatus: status,
        phaseTimings: nextTimings,
      };
    }),
}));

useSessionStore.subscribe(
  (s) => s.strategyId,
  (current, previous) => {
    if (previous != null && previous !== "" && current !== previous) {
      usePlanStore.getState().clearPlan();
      usePlanStore.getState().clearThoughts();
      usePlanStore.getState().clearPhase();
    }
  },
);
