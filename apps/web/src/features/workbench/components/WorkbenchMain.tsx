"use client";

import { useWorkbenchStore } from "../store";
import { useSessionStore } from "@/state/useSessionStore";
import { EmptyState } from "@/lib/components/ui/EmptyState";
import { Layers } from "lucide-react";
import { WorkbenchChat } from "./WorkbenchChat";
import { SOURCE_CONFIG } from "./geneSetSourceConfig";
import {
  EnrichmentPanel,
  DistributionsPanel,
  EvaluatePanel,
  CustomEnrichmentPanel,
  SweepPanel,
  ResultsTablePanel,
  StepContributionPanel,
  BatchPanel,
  BenchmarkPanel,
  EnsemblePanel,
  ConfidencePanel,
  ReverseSearchPanel,
} from "./panels";

// ---------------------------------------------------------------------------
// Active set header — rich version
// ---------------------------------------------------------------------------

function ActiveSetHeader() {
  const geneSets = useWorkbenchStore((s) => s.geneSets);
  const activeSetId = useWorkbenchStore((s) => s.activeSetId);
  const activeSet = geneSets.find((gs) => gs.id === activeSetId);

  if (!activeSet) return null;

  const colorClass = SOURCE_CONFIG[activeSet.source].badgeClass;

  return (
    <div className="mb-4 px-4 py-3 animate-fade-in">
      <div className="flex items-center gap-3">
        <h1 className="text-base font-semibold text-foreground">{activeSet.name}</h1>
        <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground tabular-nums">
          {activeSet.geneCount.toLocaleString()} genes
        </span>
        <span
          className={`rounded-full border px-2 py-0.5 text-[10px] font-medium capitalize ${colorClass}`}
        >
          {activeSet.source}
        </span>
        <span className="text-xs text-muted-foreground">{activeSet.siteId}</span>
      </div>
      {activeSet.searchName != null && activeSet.searchName !== "" && (
        <p className="mt-1 text-xs text-muted-foreground">
          {activeSet.searchName}
          {activeSet.parameters != null &&
            Object.entries(activeSet.parameters)
              .slice(0, 3)
              .map(([k, v]) => ` \u00b7 ${k}: ${String(v)}`)
              .join("")}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panel list with staggered animation
// ---------------------------------------------------------------------------

const PANELS = [
  ResultsTablePanel,
  EnrichmentPanel,
  DistributionsPanel,
  EvaluatePanel,
  StepContributionPanel,
  ConfidencePanel,
  EnsemblePanel,
  ReverseSearchPanel,
  BatchPanel,
  BenchmarkPanel,
  CustomEnrichmentPanel,
  SweepPanel,
];

// ---------------------------------------------------------------------------
// Main content area
// ---------------------------------------------------------------------------

export function WorkbenchMain() {
  const activeSetId = useWorkbenchStore((s) => s.activeSetId);
  const lastExperiment = useWorkbenchStore((s) => s.lastExperiment);
  const selectedSite = useSessionStore((s) => s.selectedSite);

  if (activeSetId == null) {
    return (
      <EmptyState
        icon={<Layers className="h-10 w-10" />}
        heading="Welcome to the Workbench"
        description="Add a gene set to get started. Paste gene IDs, import from a strategy, or upload a file."
      />
    );
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      {/* Key on activeSetId so all panels remount (reset local state) on gene set switch */}
      <div key={activeSetId} className="mx-auto w-full max-w-5xl space-y-3 p-6">
        <ActiveSetHeader />
        <WorkbenchChat
          experimentId={lastExperiment?.id ?? null}
          siteId={selectedSite}
        />
        {PANELS.map((Panel, i) => (
          <div
            key={i}
            className="animate-fade-in"
            style={{
              animationDelay: `${i * 40}ms`,
              animationFillMode: "backwards",
            }}
          >
            <Panel />
          </div>
        ))}
      </div>
    </div>
  );
}
