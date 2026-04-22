"use client";

import { useRouter } from "next/navigation";
import { ExternalLink, Workflow } from "lucide-react";

import type { Strategy } from "@pathfinder/shared";
import { Button } from "@/components/ui/button";
import { CompactStrategyView } from "@/features/strategy/graph/components/CompactStrategyView";

import { RailEmptyState, RailPanelShell } from "./RailPanelShell";

interface StrategyPanelProps {
  strategy: Strategy | null;
  siteId: string;
}

export function StrategyPanel({ strategy, siteId }: StrategyPanelProps) {
  const router = useRouter();
  const hasSteps = strategy != null && strategy.steps.length > 0;

  const openFullEditor = (): void => {
    if (strategy == null) return;
    router.push(`/${siteId}/conversation/${strategy.id}/strategy`);
  };

  const openStep = (stepId: string): void => {
    if (strategy == null) return;
    router.push(`/${siteId}/conversation/${strategy.id}/strategy/step/${stepId}`);
  };

  return (
    <RailPanelShell
      title="Strategy"
      headerActions={
        hasSteps ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={openFullEditor}
            data-testid="rail-strategy-open"
            className="h-7 gap-1 px-2 text-xs"
          >
            Open
            <ExternalLink className="size-3" aria-hidden />
          </Button>
        ) : null
      }
    >
      {hasSteps ? (
        <div className="flex h-full flex-col" data-testid="rail-strategy-panel">
          <div className="min-h-0 flex-1 overflow-auto">
            <CompactStrategyView
              strategy={strategy}
              onStepClick={openStep}
            />
          </div>
          <StrategyFooter strategy={strategy} />
        </div>
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

interface StrategyFooterProps {
  strategy: Strategy;
}

function StrategyFooter({ strategy }: StrategyFooterProps) {
  const stepCount = strategy.steps.length;
  return (
    <div
      className="border-t border-border px-3 py-2 text-[10px] text-muted-foreground"
      data-testid="rail-strategy-footer"
    >
      {stepCount} {stepCount === 1 ? "step" : "steps"}
    </div>
  );
}
