import { useState } from "react";
import type { Experiment } from "@pathfinder/shared";
import {
  ArrowLeft,
  BarChart3,
  Download,
  FileText,
  FlaskConical,
  GitBranch,
  GitCompare,
  RotateCcw,
  Settings,
  Sparkles,
  Table,
} from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { Badge } from "@/lib/components/ui/Badge";
import { exportExperiment } from "../../api";
import { useExperimentViewStore } from "../../store";
import { TabErrorBoundary, NoStrategyNotice } from "./shared/DashboardShared";
import { OverviewTab } from "./OverviewTab";
import { AnalysesTabs } from "./analysis/AnalysesTabs";
import { NotesEditor } from "./shared/NotesEditor";
import { ConfigSection } from "./shared/ConfigSection";
import { ResultsTable } from "./tabs/ResultsTable";
import { StrategyGraph } from "./shared/StrategyGraph";

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

export function ResultsDashboard({ experiment, siteId }: ResultsDashboardProps) {
  const {
    setView,
    loadCompareExperiment,
    loadExperiment,
    experiments,
    optimizeFromEvaluation,
  } = useExperimentViewStore();
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  const parentId = experiment.config.parentExperimentId;
  const parentName = parentId
    ? (experiments.find((e) => e.id === parentId)?.name ?? parentId)
    : null;

  const wasOptimized = !!experiment.optimizationResult;

  return (
    <div data-testid="results-dashboard" className="h-full overflow-y-auto">
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
                Export CSV
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  const { getExperimentReport } = await import("../../api/controlSets");
                  await getExperimentReport(experiment.id);
                }}
              >
                <FileText className="h-3.5 w-3.5" />
                HTML Report
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  const mode = experiment.config.mode;
                  const isMultiStep = mode === "multi-step" || mode === "import";
                  setView(isMultiStep ? "multi-step-setup" : "setup");
                }}
              >
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
            <OverviewTab
              experiment={experiment}
              siteId={siteId}
              onOptimize={() => optimizeFromEvaluation(experiment.id)}
            />
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
