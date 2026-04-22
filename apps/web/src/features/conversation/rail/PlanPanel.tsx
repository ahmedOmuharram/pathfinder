"use client";

import type { PlannedStep } from "@pathfinder/shared";
import { ClipboardList } from "lucide-react";

import { usePlanStore } from "@/state/usePlanStore";

import { RailEmptyState, RailPanelShell } from "./RailPanelShell";

export function PlanPanel() {
  const artifact = usePlanStore((s) => s.activePlanArtifact);
  return (
    <RailPanelShell title="Plan">
      {artifact == null ? (
        <RailEmptyState
          icon={<ClipboardList className="h-8 w-8" aria-hidden />}
          heading="No plan proposed yet"
          description="The planning agent will propose a reviewable plan here. Approve or reject it before execution."
        />
      ) : (
        <div className="space-y-3 p-3 text-sm">
          {artifact.rationale !== "" && (
            <section>
              <h3 className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                Rationale
              </h3>
              <p className="text-xs leading-relaxed text-foreground">{artifact.rationale}</p>
            </section>
          )}
          <section>
            <h3 className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              {artifact.steps.length} {artifact.steps.length === 1 ? "step" : "steps"}
            </h3>
            <ol className="space-y-3">
              {artifact.steps.map((step, idx) => (
                <PlanStepCard key={`${step.searchName}-${idx}`} step={step} index={idx} />
              ))}
            </ol>
          </section>
        </div>
      )}
    </RailPanelShell>
  );
}

function PlanStepCard({ step, index }: { step: PlannedStep; index: number }) {
  const params = step.parameters ?? {};
  const paramEntries = Object.entries(params).filter(
    ([, value]) => value !== null && value !== undefined && value !== "",
  );
  return (
    <li className="rounded-md border border-border bg-card/60 p-2.5">
      <div className="flex items-baseline gap-2">
        <span className="text-xs font-semibold text-muted-foreground tabular-nums">
          {index + 1}.
        </span>
        <span className="break-all font-mono text-xs text-foreground">{step.searchName}</span>
      </div>
      {step.rationale != null && step.rationale !== "" && (
        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
          {step.rationale}
        </p>
      )}
      {paramEntries.length > 0 && (
        <dl className="mt-2 space-y-1 border-t border-border/60 pt-2">
          {paramEntries.map(([key, value]) => (
            <div key={key} className="flex gap-2 text-[11px]">
              <dt className="w-32 shrink-0 break-all font-mono text-muted-foreground">
                {key}
              </dt>
              <dd className="min-w-0 flex-1 break-words font-mono text-foreground">
                {formatParamValue(value)}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </li>
  );
}

function formatParamValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}
