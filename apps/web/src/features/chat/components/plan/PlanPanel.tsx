"use client";

import { useShallow } from "zustand/react/shallow";
import { usePlanStore } from "@/state/usePlanStore";
import { useCurrentStrategy } from "@/state/useStrategySelectors";
import { StrategyLifecycleBadge } from "@/features/chat/components/phase/StrategyLifecycleBadge";
import { PlanThinkingBlock } from "./PlanThinkingBlock";
import { PlanPhaseTimingBlock } from "./PlanPhaseTimingBlock";
import { StrategyPlanCard } from "./StrategyPlanCard";

interface PlanPanelProps {
  siteId: string;
  onClose: () => void;
  onCollapse: () => void;
}

export function PlanPanel({ siteId, onClose, onCollapse }: PlanPanelProps) {
  const { strategy } = useCurrentStrategy();
  const {
    activePlan,
    activePlanTraceId,
    activePlanMessageGroupId,
    currentPhase,
    phaseStatus,
    planThoughts,
    phaseTimings,
    sendMessage,
    submitPlanAction,
  } = usePlanStore(
    useShallow((s) => ({
      activePlan: s.activePlan,
      activePlanTraceId: s.activePlanTraceId,
      activePlanMessageGroupId: s.activePlanMessageGroupId,
      currentPhase: s.currentPhase,
      phaseStatus: s.phaseStatus,
      planThoughts: s.planThoughts,
      phaseTimings: s.phaseTimings,
      sendMessage: s.sendMessage,
      submitPlanAction: s.submitPlanAction,
    })),
  );
  if (activePlan == null) return null;

  const noopSend = (_text: string, _metadata?: Record<string, unknown>) => {};
  const noopApprove = async () => {};

  return (
    <div className="flex h-full flex-col overflow-hidden border-l border-border bg-card">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <span className="text-sm">{"\u{1F4CB}"}</span>
        <h2 className="flex-1 text-sm font-semibold text-foreground">Strategy Plan</h2>
        <StrategyLifecycleBadge
          stepCount={strategy?.stepCount ?? strategy?.steps.length ?? activePlan.steps.length}
          wdkStrategyId={strategy?.wdkStrategyId ?? null}
          isSaved={strategy?.isSaved ?? false}
          isActiveStreaming={currentPhase != null && phaseStatus != null}
          currentPhase={currentPhase}
          phaseStatus={phaseStatus}
        />
        <button
          type="button"
          onClick={onCollapse}
          className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          aria-label="Collapse plan panel"
        >
          {"\u25B6"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          aria-label="Close plan panel"
        >
          {"\u2715"}
        </button>
      </div>

      {/* Scrollable plan content */}
      <div className="min-h-0 flex-1 overflow-y-auto p-1">
        {/* Plan thinking blocks */}
        {planThoughts.length > 0 && (
          <div className="px-2 pt-2">
            <PlanThinkingBlock thoughts={planThoughts} isLive={false} />
          </div>
        )}

        <PlanPhaseTimingBlock phaseTimings={phaseTimings} />

        {/* Interactive plan card */}
        <StrategyPlanCard
          siteId={siteId}
          plan={activePlan}
          planTraceId={activePlanTraceId}
          planMessageGroupId={activePlanMessageGroupId}
          onSendMessage={sendMessage ?? noopSend}
          onApprovePlan={submitPlanAction ?? noopApprove}
        />
      </div>
    </div>
  );
}
