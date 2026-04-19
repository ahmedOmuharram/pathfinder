"use client";

import { Workflow } from "lucide-react";

import type { Strategy } from "@pathfinder/shared";
import { StrategyGraph } from "@/features/strategy/graph/components/StrategyGraph";

import { RailEmptyState, RailPanelShell } from "./RailPanelShell";

interface StrategyPanelProps {
  strategy: Strategy | null;
  siteId: string;
}

export function StrategyPanel({ strategy, siteId }: StrategyPanelProps) {
  const hasSteps = strategy != null && strategy.steps.length > 0;
  return (
    <RailPanelShell title="Strategy">
      {hasSteps ? (
        <StrategyGraph strategy={strategy} siteId={siteId} />
      ) : (
        <RailEmptyState
          icon={<Workflow className="h-8 w-8" aria-hidden />}
          heading="No strategy built yet"
          description="The execution agent will build a WDK strategy here once the plan is approved."
        />
      )}
    </RailPanelShell>
  );
}
