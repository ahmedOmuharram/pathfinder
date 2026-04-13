import { usePlanStore } from "@/state/usePlanStore";
import type {
  DecisionPresentedData,
  PhaseChangeData,
  PlanApprovedData,
  PlanPresentedData,
  PlanUpdatedData,
  PlanningThoughtData,
} from "@/lib/sse_events";
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
  ctx: ChatEventContext,
  data: PlanPresentedData,
): void {
  const parsed = InteractivePlanSchema.safeParse(data.plan);
  if (!parsed.success) {
    console.error("[plan] Failed to parse plan:", parsed.error.message);
    return;
  }
  const store = usePlanStore.getState();
  store.setPlan(parsed.data);
  store.setPlanTraceContext({
    traceId: null,
    messageGroupId: ctx.streamState.messageGroupId ?? null,
  });
}

export function handlePlanApprovedEvent(
  ctx: ChatEventContext,
  data: PlanApprovedData,
): void {
  const parsed = InteractivePlanSchema.safeParse(data.plan);
  if (!parsed.success) {
    console.error("[plan] Failed to parse approved plan:", parsed.error.message);
    return;
  }
  const store = usePlanStore.getState();
  store.setPlan(parsed.data);
  store.setPlanTraceContext({
    traceId: null,
    messageGroupId: ctx.streamState.messageGroupId ?? null,
  });
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
  ctx: ChatEventContext,
  data: PhaseChangeData,
): void {
  if (
    data.status === "started" &&
    typeof data.messageId === "string" &&
    data.messageId !== ""
  ) {
    // Only reset the cached index when the messageId actually CHANGES.
    // Resetting on every phase_change (even for the same message) forces a
    // re-lookup that can fail if the message hasn't been inserted yet,
    // which leads to a duplicate message being appended.
    const prevMessageId = ctx.streamState.streamingAssistantMessageId;
    if (prevMessageId !== data.messageId) {
      ctx.streamState.streamingAssistantIndex = null;
    }
    ctx.streamState.streamingAssistantMessageId = data.messageId;
    ctx.thinking.setActiveMessage(data.messageId);
  }
  if (data.status !== "started") {
    ctx.thinking.setActiveMessage(null);
  }
  if (
    data.status === "started" &&
    typeof data.messageGroupId === "string" &&
    data.messageGroupId !== ""
  ) {
    ctx.streamState.messageGroupId = data.messageGroupId;
  }
  if (typeof data.phase === "string") {
    ctx.streamState.currentPhase = data.phase;
    const pipeline = ctx.streamState.pipeline;
    const phaseConfig =
      data.phase === "scoping" ? pipeline?.scoping
        : data.phase === "discovery" ? pipeline?.discovery
          : data.phase === "planning" ? pipeline?.planning
            : data.phase === "execution" ? pipeline?.execution
              : data.phase === "verification" ? pipeline?.verification
                : undefined;
    if (phaseConfig?.modelId != null) {
      ctx.streamState.currentModelId = phaseConfig.modelId;
    }
  }
  usePlanStore
    .getState()
    .setPhase(data.phase, data.status, {
      emittedAt: data.emittedAt ?? null,
      phaseStartedAt: data.phaseStartedAt ?? null,
      phaseCompletedAt: data.phaseCompletedAt ?? null,
      durationMs: data.durationMs ?? null,
    });
}
