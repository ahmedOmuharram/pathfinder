"use client";

import { cn } from "@/lib/utils/cn";
import {
  formatPipelinePhaseLabel,
  formatPipelineStatusLabel,
} from "@/features/chat/components/phase/phaseUi";

interface StrategyLifecycleStatusInput {
  stepCount?: number | null;
  wdkStrategyId?: number | null;
  isSaved?: boolean | null;
  isActiveStreaming?: boolean;
  currentPhase?: string | null;
  phaseStatus?: string | null;
}

interface StrategyLifecycleDescriptor {
  label: string;
  tone: string;
}

function lifecycleDetailLabel(
  phase: string | null | undefined,
  status: string | null | undefined,
): string | null {
  if (phase == null || phase === "" || status == null || status === "") return null;
  if (status === "awaiting_approval" || status === "awaiting_input" || status === "failed") {
    return formatPipelineStatusLabel(status);
  }
  return formatPipelinePhaseLabel(phase);
}

function lifecycleTone(baseLabel: string, phaseStatus: string | null | undefined): string {
  if (phaseStatus === "failed") return "bg-destructive/10 text-destructive";
  if (phaseStatus === "awaiting_approval" || phaseStatus === "awaiting_input") {
    return "bg-warning/10 text-warning";
  }
  if (baseLabel === "Building") return "bg-warning/10 text-warning";
  if (baseLabel === "Saved") return "bg-success/10 text-success";
  return "bg-muted text-muted-foreground";
}

export function getStrategyLifecycleDescriptor(
  input: StrategyLifecycleStatusInput,
): StrategyLifecycleDescriptor | null {
  const stepCount = input.stepCount ?? 0;
  const hasPersistedContent =
    stepCount > 0 || input.wdkStrategyId != null || input.isSaved === true;
  const hasLivePhase =
    input.currentPhase != null &&
    input.currentPhase !== "" &&
    input.phaseStatus != null &&
    input.phaseStatus !== "";
  const isLive = input.isActiveStreaming === true || hasLivePhase;

  if (!hasPersistedContent && !isLive) return null;

  let baseLabel = "Draft";
  if (!hasPersistedContent && isLive) {
    baseLabel = "Building";
  } else if (input.isSaved === true) {
    baseLabel = "Saved";
  } else if (input.isActiveStreaming === true && input.wdkStrategyId == null) {
    baseLabel = "Building";
  }

  const detail = lifecycleDetailLabel(input.currentPhase, input.phaseStatus);
  return {
    label: detail == null ? baseLabel : `${baseLabel} • ${detail}`,
    tone: lifecycleTone(baseLabel, input.phaseStatus),
  };
}

interface StrategyLifecycleBadgeProps extends StrategyLifecycleStatusInput {
  className?: string;
}

export function StrategyLifecycleBadge(props: StrategyLifecycleBadgeProps) {
  const descriptor = getStrategyLifecycleDescriptor(props);
  if (descriptor == null) return null;

  return (
    <span
      className={cn(
        "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        descriptor.tone,
        props.className,
      )}
    >
      {descriptor.label}
    </span>
  );
}
