import type { Experiment } from "@pathfinder/shared";
import { ArrowLeft, Download, GitCompare, RotateCcw } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { Badge } from "@/lib/components/ui/Badge";
import { Separator } from "@/lib/components/ui/Separator";
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

interface ResultsDashboardProps {
  experiment: Experiment;
  siteId: string;
}

export function ResultsDashboard({ experiment, siteId }: ResultsDashboardProps) {
  const { setView, loadCompareExperiment, loadExperiment, experiments } =
    useExperimentStore();
  const metrics = experiment.metrics;
  const parentId = experiment.config.parentExperimentId;
  const parentName = parentId
    ? (experiments.find((e) => e.id === parentId)?.name ?? parentId)
    : null;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-8 px-8 py-6 animate-fade-in">
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
            </div>
          </div>
        </header>

        <Separator />

        <NotesEditor
          experimentId={experiment.id}
          initialNotes={experiment.notes ?? ""}
        />

        <AiInterpretation experiment={experiment} siteId={siteId} />

        {metrics && <MetricsOverview metrics={metrics} />}
        {metrics && <ConfusionMatrixSection cm={metrics.confusionMatrix} />}
        <GeneListsSection experiment={experiment} />
        {experiment.crossValidation && (
          <CrossValidationSection cv={experiment.crossValidation} />
        )}
        {experiment.enrichmentResults.length > 0 && (
          <EnrichmentSection results={experiment.enrichmentResults} />
        )}
        {experiment.optimizationResult && (
          <OptimizationSection result={experiment.optimizationResult} />
        )}
        <ThresholdSweepSection experiment={experiment} />
        <CustomEnrichmentSection experimentId={experiment.id} />
        <ConfigSection experiment={experiment} />
      </div>
    </div>
  );
}
