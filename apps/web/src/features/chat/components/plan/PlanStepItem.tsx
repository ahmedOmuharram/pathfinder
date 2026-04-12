"use client";

import { type ReactNode, useState } from "react";
import { AlertTriangle, HelpCircle, Loader2, CheckCircle2, XCircle } from "lucide-react";

import type { PlannedStep, StepStatus } from "@/lib/types/plan";
import { PlanParameterEditor } from "@/features/chat/components/plan/PlanParameterEditor";

interface PlanStepItemProps {
  siteId: string;
  step: PlannedStep;
  index: number;
  onParamChange: (stepId: string, paramName: string, value: unknown) => void;
  disabled: boolean;
}

const statusLabel: Record<StepStatus, string> = {
  ready: "Ready",
  needs_discovery: "Needs discovery",
  needs_user_input: "Needs your input",
  executing: "Executing",
  complete: "Complete",
  failed: "Failed",
};

const statusIcon: Record<StepStatus, ReactNode> = {
  ready: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
  needs_discovery: <AlertTriangle className="h-4 w-4 text-amber-500" />,
  needs_user_input: <HelpCircle className="h-4 w-4 text-blue-500" />,
  executing: <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />,
  complete: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
  failed: <XCircle className="h-4 w-4 text-destructive" />,
};

export function PlanStepItem({
  siteId,
  step,
  index,
  onParamChange,
  disabled,
}: PlanStepItemProps) {
  const needsAttention = step.status === "needs_discovery" || step.status === "needs_user_input";
  const [expanded, setExpanded] = useState(needsAttention);

  return (
    <div className="rounded-md border border-border bg-card">
      {/* Collapsed header */}
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        <span aria-label={statusLabel[step.status]}>
          {statusIcon[step.status]}
        </span>
        <span className="text-xs font-medium tabular-nums text-muted-foreground">
          {index + 1}.
        </span>
        <span className="flex-1 truncate text-sm font-medium text-foreground">
          {step.displayName}
        </span>
        {step.operator !== null && step.operator !== "" && (
          <span className="rounded-md border border-border bg-muted px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            {step.operator}
          </span>
        )}
        {step.expectedCount !== null && (
          <span className="text-xs tabular-nums text-muted-foreground">
            ~{step.expectedCount.toLocaleString()}
          </span>
        )}
        <span
          className={`text-xs text-muted-foreground transition-transform ${expanded ? "rotate-90" : ""}`}
          aria-hidden="true"
        >
          &#9654;
        </span>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-border px-3 py-2 space-y-3">
          {/* Rationale */}
          <p className="text-xs leading-snug text-muted-foreground">{step.rationale}</p>

          {/* Search name */}
          <div className="text-[11px] text-muted-foreground">
            Search: <span className="font-medium text-foreground">{step.searchName}</span>
            {" "}&middot;{" "}
            {step.recordType}
          </div>

          {/* Parameters */}
          <PlanParameterEditor
            siteId={siteId}
            step={step}
            onParamChange={(paramName, value) => onParamChange(step.id, paramName, value)}
            disabled={disabled}
          />

          {/* Actual count if available */}
          {step.actualCount !== null && (
            <div className="text-[11px] text-muted-foreground">
              Actual results: <span className="font-semibold tabular-nums text-foreground">{step.actualCount.toLocaleString()}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
