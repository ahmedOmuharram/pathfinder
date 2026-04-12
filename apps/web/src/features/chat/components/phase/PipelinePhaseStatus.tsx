"use client";

import { cn } from "@/lib/utils/cn";
import {
  formatPipelineDuration,
  formatPipelinePhaseLabel,
  formatPipelineStatusLabel,
  pipelineStatusTone,
} from "./phaseUi";

interface PipelinePhaseStatusProps {
  phase: string | null;
  status: string | null;
  durationMs?: number | null;
  variant?: "card" | "pill";
  label?: string;
}

export function PipelinePhaseStatus({
  phase,
  status,
  durationMs = null,
  variant = "card",
  label = "Current phase",
}: PipelinePhaseStatusProps) {
  if (phase == null || phase === "" || status == null || status === "") return null;

  const tone = pipelineStatusTone(status);
  const phaseLabel = formatPipelinePhaseLabel(phase);
  const statusLabel = formatPipelineStatusLabel(status);
  const durationLabel = formatPipelineDuration(durationMs, status);

  if (variant === "pill") {
    return (
      <div
        className={cn(
          "inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] font-medium",
          tone,
        )}
      >
        <span>{phaseLabel}</span>
        <span className="opacity-75">•</span>
        <span>{statusLabel}</span>
        <span className="opacity-75">•</span>
        <span>{durationLabel}</span>
      </div>
    );
  }

  return (
    <section className="mx-2 mt-2 overflow-hidden rounded-lg border border-border/70 bg-background/50">
      <div className="border-b border-border/70 px-3 py-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          {label}
        </p>
      </div>
      <div className="flex items-center justify-between gap-3 px-3 py-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">{phaseLabel}</p>
          <p className="text-xs text-muted-foreground">{statusLabel}</p>
        </div>
        <div
          className={cn(
            "rounded-full border px-2.5 py-1 text-xs font-semibold",
            tone,
          )}
        >
          {durationLabel}
        </div>
      </div>
    </section>
  );
}
