"use client";

import type { Step } from "@pathfinder/shared";
import { Skeleton } from "@/components/ui/skeleton";
import type { StepSnapshot } from "@/state/strategy/useStepSnapshot";
import { ZeroResultHoverCard } from "./ZeroResultHoverCard";

export type ResultLabelProps = {
  step: Step;
  snapshot: StepSnapshot;
};

function pluralizedRecord(step: Step, count: number): string {
  const base =
    step.recordType != null && step.recordType !== "" ? step.recordType : "result";
  return count === 1 ? base : `${base}s`;
}

export function ResultLabel({ step, snapshot }: ResultLabelProps) {
  if (snapshot.isInvalid || snapshot.isFailed) return null;
  const count = snapshot.estimatedSize;

  if (count === 0) {
    return <ZeroResultHoverCard step={step} count={0} />;
  }

  if (typeof count === "number") {
    return (
      <span className="font-mono text-xs text-muted-foreground">
        {count.toLocaleString()} {pluralizedRecord(step, count)}
      </span>
    );
  }

  if (snapshot.isBusy) {
    return (
      <Skeleton data-testid="step-count-skeleton" className="h-3 w-16 rounded-sm" />
    );
  }

  return (
    <span className="font-mono text-xs text-muted-foreground/70">
      ? {pluralizedRecord(step, 0)}
    </span>
  );
}
