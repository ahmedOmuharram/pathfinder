import type { Experiment } from "@pathfinder/shared";
import { ArrowLeft, Download, GitCompare, RotateCcw } from "lucide-react";
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
      <div className="mx-auto max-w-5xl space-y-8 px-8 py-6">
        <header>
          <button
            type="button"
            onClick={() => setView("list")}
            className="mb-3 inline-flex items-center gap-1.5 text-xs text-slate-400 transition hover:text-slate-600"
          >
            <ArrowLeft className="h-3 w-3" />
            Experiments
          </button>
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h1 className="truncate text-xl font-semibold tracking-tight text-slate-900">
                {experiment.config.name}
              </h1>
              <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                <span className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[11px]">
                  {experiment.config.searchName}
                </span>
                <span>{experiment.config.recordType}</span>
                {experiment.totalTimeSeconds && (
                  <span>{experiment.totalTimeSeconds.toFixed(1)}s</span>
                )}
                {experiment.createdAt && (
                  <span>{new Date(experiment.createdAt).toLocaleDateString()}</span>
                )}
              </div>
              {parentId && parentName && (
                <div className="mt-2 flex items-center gap-1.5 text-[11px] text-slate-500">
                  <span>Derived from</span>
                  <button
                    type="button"
                    onClick={() => loadExperiment(parentId)}
                    className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 font-medium text-indigo-600 transition hover:border-indigo-200 hover:bg-indigo-50"
                  >
                    {parentName}
                  </button>
                </div>
              )}
            </div>
            <div className="flex shrink-0 gap-2">
              <button
                type="button"
                onClick={() => exportExperiment(experiment.id, experiment.config.name)}
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50"
              >
                <Download className="h-3 w-3" />
                Export
              </button>
              <button
                type="button"
                onClick={() => setView("setup")}
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50"
              >
                <RotateCcw className="h-3 w-3" />
                Re-run
              </button>
              {experiments.length > 1 && (
                <button
                  type="button"
                  onClick={() => {
                    const other = experiments.find((e) => e.id !== experiment.id);
                    if (other) loadCompareExperiment(other.id);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50"
                >
                  <GitCompare className="h-3 w-3" />
                  Compare
                </button>
              )}
            </div>
          </div>
        </header>

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
