import { Component, useState, type ReactNode } from "react";
import type { Experiment, ExperimentMetrics } from "@pathfinder/shared";
import {
  AlertCircle,
  ArrowLeft,
  BarChart3,
  Download,
  FlaskConical,
  GitBranch,
  GitCompare,
  RotateCcw,
  Sparkles,
  Settings,
  SlidersHorizontal,
  Table,
  TestTubes,
} from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { Badge } from "@/lib/components/ui/Badge";
import { exportExperiment } from "../../api";
import { useExperimentStore } from "../../store";
import { NotesEditor } from "./NotesEditor";
import { AiInterpretation } from "./AiInterpretation";
import { MetricsOverview } from "./MetricsOverview";
import { ConfusionMatrixSection } from "./ConfusionMatrixSection";
import { GeneListsSection } from "./GeneListsSection";
import { CrossValidationSection } from "./CrossValidationSection";
import { EnrichmentSection } from "./EnrichmentSection";
import { OptimizationSection } from "./OptimizationSection";
import { ThresholdSweepSection } from "./ThresholdSweepSection";
import { CustomEnrichmentSection } from "./CustomEnrichmentSection";
import { ConfigSection } from "./ConfigSection";
import { ResultsTable } from "./ResultsTable";
import { DistributionExplorer } from "./DistributionExplorer";
import { StepAnalysisPanel } from "./StepAnalysisPanel";
import { StrategyGraph } from "./StrategyGraph";
import { StepContributionPanel } from "./StepContributionPanel";
import { TreeOptimizationSection } from "./TreeOptimizationSection";

class TabErrorBoundary extends Component<
  { children: ReactNode; onReset?: () => void },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-8 text-center">
          <AlertCircle className="h-5 w-5 text-destructive" />
          <p className="text-sm font-medium text-destructive">
            Something went wrong loading this tab.
          </p>
          <p className="max-w-md text-xs text-muted-foreground">
            {this.state.error.message}
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              this.setState({ error: null });
              this.props.onReset?.();
            }}
          >
            Try again
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}

const TABS = [
  { id: "overview", label: "Overview", icon: BarChart3 },
  { id: "results", label: "Results Table", icon: Table },
  { id: "analyses", label: "Analyses", icon: FlaskConical },
  { id: "strategy", label: "Strategy", icon: GitBranch },
  { id: "config", label: "Config", icon: Settings },
] as const;

type TabId = (typeof TABS)[number]["id"];

interface ResultsDashboardProps {
  experiment: Experiment;
  siteId: string;
}

function getVerdict(metrics: ExperimentMetrics) {
  const { f1Score, sensitivity, precision } = metrics;

  if (f1Score > 0.8) {
    return {
      level: "excellent" as const,
      sentence: `Excellent search quality — F1 ${f1Score.toFixed(2)}, sensitivity ${sensitivity.toFixed(2)}`,
    };
  }
  if (f1Score > 0.6) {
    return {
      level: "good" as const,
      sentence: `Good search quality — F1 ${f1Score.toFixed(2)}, precision ${precision.toFixed(2)}`,
    };
  }
  if (f1Score > 0.4) {
    if (sensitivity > precision) {
      return {
        level: "moderate" as const,
        sentence: `High recall, low precision — many false positives (F1 ${f1Score.toFixed(2)})`,
      };
    }
    return {
      level: "moderate" as const,
      sentence: `Moderate search quality — F1 ${f1Score.toFixed(2)}, sensitivity ${sensitivity.toFixed(2)}`,
    };
  }
  return {
    level: "poor" as const,
    sentence: `Poor search quality — F1 ${f1Score.toFixed(2)}, consider adjusting parameters`,
  };
}

const VERDICT_STYLES = {
  excellent:
    "border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-300",
  good: "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300",
  moderate:
    "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300",
  poor: "border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300",
} as const;

const VERDICT_BADGE_STYLES = {
  excellent:
    "border-green-300 bg-green-100 text-green-900 dark:border-green-700 dark:bg-green-900 dark:text-green-200",
  good: "border-blue-300 bg-blue-100 text-blue-900 dark:border-blue-700 dark:bg-blue-900 dark:text-blue-200",
  moderate:
    "border-amber-300 bg-amber-100 text-amber-900 dark:border-amber-700 dark:bg-amber-900 dark:text-amber-200",
  poor: "border-red-300 bg-red-100 text-red-900 dark:border-red-700 dark:bg-red-900 dark:text-red-200",
} as const;

function SummaryVerdict({
  metrics,
}: {
  metrics: ExperimentMetrics | null | undefined;
}) {
  if (!metrics) return null;

  const { level, sentence } = getVerdict(metrics);

  return (
    <div
      className={`flex items-center gap-3 rounded-lg border px-4 py-3 ${VERDICT_STYLES[level]}`}
    >
      <Badge
        className={`shrink-0 text-xs font-semibold capitalize ${VERDICT_BADGE_STYLES[level]}`}
      >
        {level}
      </Badge>
      <span className="text-sm font-medium">{sentence}</span>
    </div>
  );
}

function NoStrategyNotice({ label }: { label?: string } = {}) {
  return (
    <div className="rounded-lg border border-border bg-muted/30 px-5 py-8 text-center text-sm text-muted-foreground">
      <AlertCircle className="mx-auto mb-2 h-5 w-5" />
      {label ??
        "This feature requires a persisted WDK strategy. Re-run the experiment to enable result browsing."}
    </div>
  );
}

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

function AnalysesTabs({ experiment }: { experiment: Experiment }) {
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

export function ResultsDashboard({ experiment, siteId }: ResultsDashboardProps) {
  const {
    setView,
    loadCompareExperiment,
    loadExperiment,
    experiments,
    optimizeFromEvaluation,
  } = useExperimentStore();
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  const metrics = experiment.metrics;
  const parentId = experiment.config.parentExperimentId;
  const parentName = parentId
    ? (experiments.find((e) => e.id === parentId)?.name ?? parentId)
    : null;

  const wasOptimized =
    !!experiment.optimizationResult || !!experiment.treeOptimizationDiff;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-8 py-6 animate-fade-in">
        <header>
          <button
            type="button"
            onClick={() => setView("list")}
            className="mb-3 inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors duration-150 hover:text-foreground"
          >
            <ArrowLeft className="h-3 w-3" />
            Experiments
          </button>
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h1 className="truncate text-xl font-semibold tracking-tight text-foreground">
                {experiment.config.name}
              </h1>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Badge
                  className={`text-xs font-semibold ${
                    wasOptimized
                      ? "border-purple-300 bg-purple-100 text-purple-900 dark:border-purple-700 dark:bg-purple-900 dark:text-purple-200"
                      : "border-blue-300 bg-blue-100 text-blue-900 dark:border-blue-700 dark:bg-blue-900 dark:text-blue-200"
                  }`}
                >
                  {wasOptimized ? "Optimized" : "Evaluation"}
                </Badge>
                <Badge variant="outline" className="font-mono text-xs">
                  {experiment.config.searchName}
                </Badge>
                <Badge variant="secondary" className="text-xs">
                  {experiment.config.recordType}
                </Badge>
                {experiment.totalTimeSeconds && (
                  <span className="text-xs text-muted-foreground">
                    {experiment.totalTimeSeconds.toFixed(1)}s
                  </span>
                )}
                {experiment.createdAt && (
                  <span className="text-xs text-muted-foreground">
                    {new Date(experiment.createdAt).toLocaleDateString()}
                  </span>
                )}
              </div>
              {parentId && parentName && (
                <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span>Derived from</span>
                  <button
                    type="button"
                    onClick={() => loadExperiment(parentId)}
                    className="rounded-md border border-border bg-muted px-2 py-0.5 font-medium text-primary transition-colors duration-150 hover:border-primary/30 hover:bg-primary/5"
                  >
                    {parentName}
                  </button>
                </div>
              )}
            </div>
            <div className="flex shrink-0 gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => exportExperiment(experiment.id, experiment.config.name)}
              >
                <Download className="h-3.5 w-3.5" />
                Export
              </Button>
              <Button variant="outline" size="sm" onClick={() => setView("setup")}>
                <RotateCcw className="h-3.5 w-3.5" />
                Re-run
              </Button>
              {experiments.length > 1 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const other = experiments.find((e) => e.id !== experiment.id);
                    if (other) loadCompareExperiment(other.id);
                  }}
                >
                  <GitCompare className="h-3.5 w-3.5" />
                  Compare
                </Button>
              )}
              {!wasOptimized && (
                <Button size="sm" onClick={() => optimizeFromEvaluation(experiment.id)}>
                  <Sparkles className="h-3.5 w-3.5" />
                  Optimize This
                </Button>
              )}
            </div>
          </div>
        </header>

        <nav className="mt-6 flex gap-1 border-b border-border" role="tablist">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={activeTab === id}
              onClick={() => setActiveTab(id)}
              className={`inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm transition-colors duration-150 ${
                activeTab === id
                  ? "border-blue-500 font-semibold text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </nav>

        <div className="mt-8 space-y-8">
          {activeTab === "overview" && (
            <>
              <SummaryVerdict metrics={metrics} />
              <AiInterpretation experiment={experiment} siteId={siteId} />
              {metrics && <MetricsOverview metrics={metrics} />}
              {metrics && <ConfusionMatrixSection cm={metrics.confusionMatrix} />}
              <GeneListsSection experiment={experiment} />
              {wasOptimized && (
                <>
                  {experiment.crossValidation && (
                    <CrossValidationSection cv={experiment.crossValidation} />
                  )}
                  {experiment.enrichmentResults.length > 0 && (
                    <EnrichmentSection results={experiment.enrichmentResults} />
                  )}
                  {experiment.optimizationResult && (
                    <OptimizationSection result={experiment.optimizationResult} />
                  )}
                  {experiment.treeOptimizationDiff && (
                    <TreeOptimizationSection diff={experiment.treeOptimizationDiff} />
                  )}
                </>
              )}
              {!wasOptimized && (
                <div className="rounded-lg border border-primary/20 bg-primary/5 p-6 text-center">
                  <Sparkles className="mx-auto mb-3 h-6 w-6 text-primary" />
                  <h3 className="text-sm font-semibold text-foreground">
                    Optimize This Strategy
                  </h3>
                  <p className="mx-auto mt-1.5 max-w-md text-sm text-muted-foreground">
                    Want to improve these results? Run optimization to automatically
                    tune parameters and find a better-performing configuration.
                  </p>
                  <Button
                    className="mt-4"
                    size="sm"
                    onClick={() => optimizeFromEvaluation(experiment.id)}
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    Optimize This Strategy
                  </Button>
                </div>
              )}
            </>
          )}

          {activeTab === "results" && (
            <TabErrorBoundary>
              {experiment.wdkStepId ? (
                <ResultsTable experimentId={experiment.id} />
              ) : (
                <NoStrategyNotice />
              )}
            </TabErrorBoundary>
          )}

          {activeTab === "analyses" && (
            <TabErrorBoundary>
              <AnalysesTabs experiment={experiment} />
            </TabErrorBoundary>
          )}

          {activeTab === "strategy" && (
            <TabErrorBoundary>
              {experiment.wdkStrategyId ? (
                <StrategyGraph experimentId={experiment.id} />
              ) : (
                <NoStrategyNotice />
              )}
            </TabErrorBoundary>
          )}

          {activeTab === "config" && (
            <>
              <NotesEditor
                experimentId={experiment.id}
                initialNotes={experiment.notes ?? ""}
              />
              <ConfigSection experiment={experiment} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
