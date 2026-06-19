"use client";

import type { PlanArtifact } from "@pathfinder/shared";
import { Check } from "lucide-react";

export function ReadOnlyRecap({
  slots,
  submitted,
}: {
  slots: PlanArtifact["slots"];
  submitted: boolean;
}) {
  const hasQuestions = (slots?.length ?? 0) > 0;
  if (!submitted && !hasQuestions) return null;
  return (
    <div
      data-testid="plan-carousel-readonly"
      className="space-y-2 rounded-md border border-border bg-background/60 p-2.5"
    >
      {submitted && (
        <div className="inline-flex items-center gap-1.5 rounded-md border border-success/30 bg-success/10 px-2 py-1 text-xs text-success">
          <Check className="size-3.5" aria-hidden /> Plan submitted
        </div>
      )}
      {hasQuestions && (
        <ul className="space-y-1.5 text-xs text-muted-foreground">
          {(slots ?? []).map((s) => (
            <li key={`${s.stepId}:${s.paramName}`} className="leading-snug">
              <span className="font-mono text-foreground">{s.paramName}</span> —{" "}
              {s.question}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
