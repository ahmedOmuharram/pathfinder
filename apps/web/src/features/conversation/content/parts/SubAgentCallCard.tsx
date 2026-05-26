"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

import type {
  DataSubAgentCallPayload,
  DataSubAgentStepPayload,
} from "@pathfinder/shared";
import { useSubAgentStepsStore } from "@/state/useSubAgentStepsStore";

const EMPTY_STEPS: DataSubAgentStepPayload[] = [];

const PHASE_LABELS: Record<string, string> = {
  scoping: "Scoping",
  discovery: "Discovery",
  planning: "Planning",
  execution: "Execution",
  verification: "Verification",
  recover_failed_steps: "Recovery",
};

const STATE_STYLES: Record<DataSubAgentCallPayload["state"], string> = {
  started: "border-primary/30 bg-primary/10",
  completed: "border-emerald-500/30 bg-emerald-500/10",
  failed: "border-destructive/30 bg-destructive/10",
};

const STATE_DOT: Record<DataSubAgentCallPayload["state"], string> = {
  started: "animate-pulse bg-primary",
  completed: "bg-emerald-500",
  failed: "bg-destructive",
};

export function SubAgentCallCard({ data }: { data: DataSubAgentCallPayload }) {
  const label = PHASE_LABELS[data.phase] ?? data.phase;
  const steps = useSubAgentStepsStore(
    (s) => s.byParent[data.toolCallId] ?? EMPTY_STEPS,
  );
  const [expanded, setExpanded] = useState(false);
  const stepCount = steps.length;
  const showToggle = stepCount > 0 || data.modelId !== "";

  return (
    <div
      data-testid="data-sub-agent-call"
      className={`my-2 rounded-md border text-xs ${STATE_STYLES[data.state]}`}
    >
      <button
        type="button"
        onClick={() => setExpanded((p) => !p)}
        disabled={!showToggle}
        className="flex w-full items-center gap-2 px-3 py-2 text-left disabled:cursor-default"
      >
        {showToggle ? (
          expanded ? (
            <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
          )
        ) : (
          <span className="w-3 shrink-0" />
        )}
        <span
          className={`inline-block size-2 shrink-0 rounded-full ${STATE_DOT[data.state]}`}
        />
        <span className="font-medium text-foreground">{label}</span>
        <span className="text-muted-foreground">· {data.state}</span>
        {data.modelId !== "" && (
          <span className="ml-auto rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            {data.modelId}
          </span>
        )}
      </button>
      {data.summary !== "" && (
        <div className="px-3 pb-2 text-muted-foreground">{data.summary}</div>
      )}
      {expanded && stepCount > 0 && (
        <div className="border-t border-border/60 bg-background/50 px-3 py-2">
          <ol className="space-y-1.5">
            {steps.map((step, i) => (
              <li key={`${step.parentToolCallId}-${i}`}>
                <SubAgentStepRow step={step} />
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

function SubAgentStepRow({ step }: { step: DataSubAgentStepPayload }) {
  if (step.kind === "tool") {
    const toolName = step.toolName ?? "unknown";
    const dotClass =
      step.state === "completed"
        ? "bg-emerald-500"
        : step.state === "failed"
          ? "bg-destructive"
          : "animate-pulse bg-primary";
    return (
      <div className="flex items-start gap-2 text-[11px]">
        <span
          className={`mt-1 inline-block size-1.5 shrink-0 rounded-full ${dotClass}`}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-1">
            <span className="font-mono text-foreground">{toolName}</span>
            <span className="text-muted-foreground">{step.state}</span>
          </div>
          {step.resultSummary !== undefined && step.resultSummary !== null && step.resultSummary !== "" && (
            <div className="mt-0.5 line-clamp-2 font-mono text-[10px] text-muted-foreground">
              {step.resultSummary}
            </div>
          )}
        </div>
      </div>
    );
  }
  if (step.kind === "reasoning") {
    return (
      <div className="flex items-start gap-2 text-[11px]">
        <span className="mt-1 inline-block size-1.5 shrink-0 rounded-full bg-amber-400" />
        <div className="min-w-0 flex-1 italic text-muted-foreground">
          {step.text ?? ""}
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-start gap-2 text-[11px]">
      <span className="mt-1 inline-block size-1.5 shrink-0 rounded-full bg-foreground/40" />
      <div className="min-w-0 flex-1 text-foreground">{step.text ?? ""}</div>
    </div>
  );
}
