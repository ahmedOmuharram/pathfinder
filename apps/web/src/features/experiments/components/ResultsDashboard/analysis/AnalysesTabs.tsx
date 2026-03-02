import { useState } from "react";
import type { Experiment } from "@pathfinder/shared";
import {
  BarChart3,
  FlaskConical,
  GitBranch,
  SlidersHorizontal,
  TestTubes,
} from "lucide-react";
import { NoStrategyNotice } from "../shared/DashboardShared";
import { ThresholdSweepSection } from "./ThresholdSweepSection";
import { CustomEnrichmentSection } from "../shared/CustomEnrichmentSection";
import { DistributionExplorer } from "../tabs/DistributionExplorer";
import { StepAnalysisPanel } from "./StepAnalysisPanel";
import { StepContributionPanel } from "./StepContributionPanel";

const ANALYSIS_TABS = [
  { id: "sweep", label: "Threshold Sweep", icon: SlidersHorizontal },
  { id: "custom-enrich", label: "Gene Set Enrichment", icon: TestTubes },
  { id: "distribution", label: "Distribution", icon: BarChart3, requiresStep: true },
  {
    id: "step-analysis",
    label: "Step Analyses",
    icon: FlaskConical,
    requiresStep: true,
  },
  {
    id: "step-contribution",
    label: "Step Contribution",
    icon: GitBranch,
    requiresMultiStep: true,
  },
] as const;

type AnalysisTabId = (typeof ANALYSIS_TABS)[number]["id"];

export function AnalysesTabs({ experiment }: { experiment: Experiment }) {
  const [activeSubTab, setActiveSubTab] = useState<AnalysisTabId>("sweep");
  const hasStep = !!experiment.wdkStepId;
  const isMultiStep =
    experiment.config.mode === "multi-step" || experiment.config.mode === "import";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-1.5">
        {ANALYSIS_TABS.map(({ id, label, icon: Icon, ...rest }) => {
          const needsStep = "requiresStep" in rest && rest.requiresStep;
          const needsMultiStep = "requiresMultiStep" in rest && rest.requiresMultiStep;
          const disabled = (needsStep && !hasStep) || (needsMultiStep && !isMultiStep);
          const active = activeSubTab === id;
          return (
            <button
              key={id}
              type="button"
              disabled={disabled}
              onClick={() => setActiveSubTab(id)}
              className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition ${
                active
                  ? "border-primary bg-primary/10 text-primary"
                  : disabled
                    ? "cursor-not-allowed border-border bg-muted/30 text-muted-foreground/50"
                    : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground"
              }`}
              title={
                disabled
                  ? needsMultiStep
                    ? "Only available for multi-step experiments"
                    : "Requires a persisted WDK strategy"
                  : undefined
              }
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          );
        })}
      </div>

      <div>
        {activeSubTab === "sweep" && <ThresholdSweepSection experiment={experiment} />}
        {activeSubTab === "custom-enrich" && (
          <CustomEnrichmentSection experimentId={experiment.id} />
        )}
        {activeSubTab === "distribution" &&
          (hasStep ? (
            <DistributionExplorer experimentId={experiment.id} />
          ) : (
            <NoStrategyNotice label="Distribution explorer requires a persisted WDK strategy." />
          ))}
        {activeSubTab === "step-analysis" &&
          (hasStep ? (
            <StepAnalysisPanel experimentId={experiment.id} />
          ) : (
            <NoStrategyNotice label="Step analyses require a persisted WDK strategy." />
          ))}
        {activeSubTab === "step-contribution" && (
          <StepContributionPanel
            experimentId={experiment.id}
            stepTree={experiment.config.stepTree}
          />
        )}
      </div>
    </div>
  );
}
