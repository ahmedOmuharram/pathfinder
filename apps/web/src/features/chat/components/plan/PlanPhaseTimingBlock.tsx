"use client";

import type { PhaseTiming, TimedPipelinePhase } from "@/state/usePlanStore";
import {
  formatPipelineDuration,
  formatPipelinePhaseLabel,
  formatPipelineStatusLabel,
} from "@/features/chat/components/phase/phaseUi";

const PHASE_ORDER: TimedPipelinePhase[] = [
  "scoping",
  "discovery",
  "planning",
  "execution",
  "verification",
];

interface PlanPhaseTimingBlockProps {
  phaseTimings: Partial<Record<TimedPipelinePhase, PhaseTiming>>;
}

export function PlanPhaseTimingBlock({ phaseTimings }: PlanPhaseTimingBlockProps) {
  const visiblePhases = PHASE_ORDER
    .map((phase) => phaseTimings[phase])
    .filter((phase): phase is PhaseTiming => phase != null);

  if (visiblePhases.length === 0) return null;

  return (
    <section
      data-testid="plan-phase-timing"
      className="mx-2 mt-2 overflow-hidden rounded-lg border border-border/70 bg-background/50"
    >
      <div className="border-b border-border/70 px-3 py-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          Phase Timing
        </p>
      </div>
      <div>
        {visiblePhases.map((timing) => (
          <div
            key={timing.phase}
            data-testid={`plan-phase-timing-${timing.phase}`}
            className="grid grid-cols-[1fr_auto] gap-2 border-t border-border/50 px-3 py-2 first:border-t-0"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium text-foreground">
                {formatPipelinePhaseLabel(timing.phase)}
              </p>
              <p
                data-testid={`plan-phase-status-${timing.phase}`}
                className="text-xs text-muted-foreground"
              >
                {formatPipelineStatusLabel(timing.status)}
              </p>
            </div>
            <div className="text-right">
              <p
                data-testid={`plan-phase-duration-${timing.phase}`}
                className="text-sm font-semibold text-foreground"
              >
                {formatPipelineDuration(timing.durationMs, timing.status)}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
