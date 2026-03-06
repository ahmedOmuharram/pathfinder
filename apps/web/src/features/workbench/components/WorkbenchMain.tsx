"use client";

import { useWorkbenchStore } from "../store";
import { EmptyState } from "@/lib/components/ui/EmptyState";
import { Layers } from "lucide-react";
import {
  EnrichmentPanel,
  DistributionsPanel,
  EvaluatePanel,
  CustomEnrichmentPanel,
  AiInterpretationPanel,
  SweepPanel,
  ResultsTablePanel,
} from "./panels";

// ---------------------------------------------------------------------------
// Active set header
// ---------------------------------------------------------------------------

function ActiveSetHeader() {
  const geneSets = useWorkbenchStore((s) => s.geneSets);
  const activeSetId = useWorkbenchStore((s) => s.activeSetId);
  const activeSet = geneSets.find((gs) => gs.id === activeSetId);

  if (!activeSet) return null;

  return (
    <div className="mb-4">
      <h1 className="text-lg font-semibold">{activeSet.name}</h1>
      <p className="text-sm text-muted-foreground">
        {activeSet.geneCount.toLocaleString()} genes &middot; {activeSet.source}
        {activeSet.searchName ? ` \u00b7 ${activeSet.searchName}` : ""}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main content area
// ---------------------------------------------------------------------------

export function WorkbenchMain() {
  const geneSets = useWorkbenchStore((s) => s.geneSets);
  const activeSetId = useWorkbenchStore((s) => s.activeSetId);

  if (geneSets.length === 0) {
    return (
      <EmptyState
        icon={<Layers className="h-10 w-10" />}
        heading="Welcome to the Workbench"
        description="Add a gene set to get started. Paste gene IDs, import from a strategy, or upload a file."
      />
    );
  }

  if (!activeSetId) {
    return (
      <EmptyState
        icon={<Layers className="h-10 w-10" />}
        heading="No set selected"
        description="Select a gene set from the sidebar to view analysis panels."
      />
    );
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl space-y-3 p-6">
        <ActiveSetHeader />
        <EnrichmentPanel />
        <DistributionsPanel />
        <EvaluatePanel />
        <CustomEnrichmentPanel />
        <AiInterpretationPanel />
        <SweepPanel />
        <ResultsTablePanel />
      </div>
    </div>
  );
}
