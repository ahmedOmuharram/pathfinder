import { usePlanStore } from "@/state/usePlanStore";
import type {
  DecisionPresentedData,
  PhaseChangeData,
  PlanPresentedData,
  PlanUpdatedData,
  PlanningThoughtData,
} from "@/lib/sse_events";
import type { PhaseStatus, PipelinePhase } from "@/state/usePlanStore";
import { InteractivePlanSchema } from "@/lib/types/plan";
import type { InteractivePlan } from "@/lib/types/plan";
import type { ChatEventContext } from "./handleChatEvent.types";

export function handlePlanningThoughtEvent(
  _ctx: ChatEventContext,
  data: PlanningThoughtData,
): void {
  usePlanStore.getState().addThought(data.thought);
}

export function handlePlanPresentedEvent(
  _ctx: ChatEventContext,
  data: PlanPresentedData,
): void {
  const parsed = InteractivePlanSchema.safeParse(data.plan);
  if (!parsed.success) {
    console.error("[plan] Failed to parse plan:", parsed.error.message);
    return;
  }
  usePlanStore.getState().setPlan(parsed.data);
}

export function handlePlanUpdatedEvent(
  _ctx: ChatEventContext,
  data: PlanUpdatedData,
): void {
  const updates = data.updates as Partial<InteractivePlan>;
  usePlanStore.getState().updatePlan(updates);
}

export function handleDecisionPresentedEvent(
  _ctx: ChatEventContext,
  _data: DecisionPresentedData,
): void {
  // Decision rendering handled via message content.
}

export function handlePhaseChangeEvent(
  _ctx: ChatEventContext,
  data: PhaseChangeData,
): void {
  usePlanStore
    .getState()
    .setPhase(data.phase as PipelinePhase, data.status as PhaseStatus);
}
