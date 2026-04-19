"use client";

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
          <p className="text-xs text-muted-foreground">{artifact.rationale}</p>
          <ol className="list-inside list-decimal space-y-1 text-xs">
            {artifact.steps.map((step, idx) => (
              <li key={`${step.searchName}-${idx}`}>
                <span className="font-mono">{step.searchName}</span>
                {step.rationale != null && step.rationale.length > 0 ? (
                  <span className="ml-1 text-muted-foreground">
                    — {step.rationale}
                  </span>
                ) : null}
              </li>
            ))}
          </ol>
        </div>
      )}
    </RailPanelShell>
  );
}
