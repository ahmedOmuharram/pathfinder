"use client";

import { ClipboardList, AlertTriangle, HelpCircle } from "lucide-react";

import type { InteractivePlan } from "@/lib/types/plan";

interface PlanPinnedBarProps {
  plan: InteractivePlan;
  onApprove: () => void;
  onViewPlan: () => void;
}

export function PlanPinnedBar({ plan, onApprove, onViewPlan }: PlanPinnedBarProps) {
  const pendingCount = plan.steps.filter(
    (s) => s.status === "needs_discovery" || s.status === "needs_user_input",
  ).length;
  const unanswered = plan.questions.filter((q) => q.answer == null).length;
  const isApproved = plan.status !== "presented";

  return (
    <div className="flex items-center gap-3 border-b border-purple-500/20 bg-card/95 px-3 py-1.5 backdrop-blur-sm">
      <ClipboardList className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <span className="flex-1 truncate text-xs font-medium text-foreground">
        {plan.title}
      </span>
      {pendingCount > 0 && (
        <span className="text-[10px] text-orange-400">
          <AlertTriangle className="inline h-3 w-3" aria-hidden="true" /> {pendingCount} needs discovery
        </span>
      )}
      {unanswered > 0 && (
        <span className="text-[10px] text-yellow-400">
          <HelpCircle className="inline h-3 w-3" aria-hidden="true" /> {unanswered} unanswered
        </span>
      )}
      {!isApproved && (
        <button
          type="button"
          onClick={onApprove}
          disabled={unanswered > 0}
          className="rounded bg-purple-600 px-2 py-0.5 text-[10px] font-medium text-white hover:bg-purple-700 disabled:opacity-50"
        >
          Approve
        </button>
      )}
      <button
        type="button"
        onClick={onViewPlan}
        className="rounded border border-border px-2 py-0.5 text-[10px] text-muted-foreground hover:bg-accent"
      >
        View Plan
      </button>
    </div>
  );
}
