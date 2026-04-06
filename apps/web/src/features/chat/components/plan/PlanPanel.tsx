"use client";

import { usePlanStore } from "@/state/usePlanStore";
import { PlanThinkingBlock } from "./PlanThinkingBlock";
import { StrategyPlanCard } from "./StrategyPlanCard";

interface PlanPanelProps {
  onClose: () => void;
  onCollapse: () => void;
}

export function PlanPanel({ onClose, onCollapse }: PlanPanelProps) {
  const activePlan = usePlanStore((s) => s.activePlan);
  const planThoughts = usePlanStore((s) => s.planThoughts);
  const sendMessage = usePlanStore((s) => s.sendMessage);
  if (activePlan == null) return null;

  const noopSend = (_text: string, _metadata?: Record<string, unknown>) => {};

  return (
    <div className="flex h-full flex-col overflow-hidden border-l border-border bg-card">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <span className="text-sm">{"\u{1F4CB}"}</span>
        <h2 className="flex-1 text-sm font-semibold text-foreground">Strategy Plan</h2>
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

          {/* Interactive plan card */}
          <StrategyPlanCard plan={activePlan} onSendMessage={sendMessage ?? noopSend} />
        </div>
    </div>
  );
}
