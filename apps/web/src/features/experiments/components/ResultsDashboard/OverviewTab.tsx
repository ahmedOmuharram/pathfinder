import type { Experiment, ExperimentMetrics, RankMetrics } from "@pathfinder/shared";
import { ArrowUpDown, FlaskConical, Info, Sparkles } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { Badge } from "@/lib/components/ui/Badge";
import { AiInterpretation } from "./shared/AiInterpretation";
import { MetricsOverview } from "./metrics/MetricsOverview";
import { ConfusionMatrixSection } from "./metrics/ConfusionMatrixSection";
import { GeneListsSection } from "./shared/GeneListsSection";
import { CrossValidationSection } from "./analysis/CrossValidationSection";
import { EnrichmentSection } from "./tabs/EnrichmentSection";
import { OptimizationSection } from "./analysis/OptimizationSection";
import { RankMetricsSection } from "./metrics/RankMetricsSection";
import { RobustnessSection } from "./metrics/RobustnessSection";
import { StepDecompositionSection } from "./analysis/StepDecompositionSection";

function getVerdict(metrics: ExperimentMetrics, rankMetrics?: RankMetrics | null) {
  const p50 = rankMetrics?.precisionAtK["50"] ?? null;
  const e50 = rankMetrics?.enrichmentAtK["50"] ?? null;

  if (p50 != null && e50 != null) {
    if (e50 > 5 && p50 > 0.3) {
      return {
        level: "excellent" as const,
        sentence: `Strong enrichment — ${e50.toFixed(1)}x at K=50, P@50 ${(p50 * 100).toFixed(0)}%`,
      };
    }
    if (e50 > 2) {
      return {
        level: "good" as const,
        sentence: `Good enrichment — ${e50.toFixed(1)}x at K=50, P@50 ${(p50 * 100).toFixed(0)}%`,
      };
    }
    if (e50 > 1) {
      return {
        level: "moderate" as const,
        sentence: `Modest enrichment — ${e50.toFixed(1)}x at K=50, results slightly better than random`,
      };
    }
    return {
      level: "poor" as const,
      sentence: `No enrichment at K=50 (${e50.toFixed(1)}x) — results not better than random`,
    };
  }

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
  rankMetrics,
}: {
  metrics: ExperimentMetrics | null | undefined;
  rankMetrics?: RankMetrics | null;
}) {
  if (!metrics) return null;

  const { level, sentence } = getVerdict(metrics, rankMetrics);

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

function RankingStatusBanner({ config }: { config: Experiment["config"] }) {
  const isRanked = !!config.sortAttribute;

  if (isRanked) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 dark:border-blue-800 dark:bg-blue-950">
        <ArrowUpDown className="h-4 w-4 shrink-0 text-blue-600 dark:text-blue-400" />
        <span className="text-sm text-blue-800 dark:text-blue-300">
          <span className="font-medium">Ranked by:</span> {config.sortAttribute}{" "}
          <span className="text-blue-600 dark:text-blue-400">
            ({config.sortDirection ?? "ASC"})
          </span>
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-800 dark:bg-amber-950">
      <Info className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
      <span className="text-sm text-amber-800 dark:text-amber-300">
        This strategy produces an unordered set. Top-K metrics reflect arbitrary
        ordering and are hidden unless you enable ranking.
      </span>
    </div>
  );
}

interface OverviewTabProps {
  experiment: Experiment;
  siteId: string;
  onOptimize: () => void;
}

export function OverviewTab({ experiment, siteId, onOptimize }: OverviewTabProps) {
  const metrics = experiment.metrics;
  const wasOptimized = !!experiment.optimizationResult;
  const hasStepAnalysis = !!experiment.stepAnalysis;

  return (
    <>
      <SummaryVerdict metrics={metrics} rankMetrics={experiment.rankMetrics} />
      <RankingStatusBanner config={experiment.config} />
      <AiInterpretation experiment={experiment} siteId={siteId} />
      {metrics && (
        <MetricsOverview
          metrics={metrics}
          rankMetrics={experiment.rankMetrics}
          robustness={experiment.robustness}
        />
      )}
      {experiment.rankMetrics && (
        <RankMetricsSection rankMetrics={experiment.rankMetrics} />
      )}
      {experiment.robustness && (
        <RobustnessSection robustness={experiment.robustness} />
      )}
      {metrics && <ConfusionMatrixSection cm={metrics.confusionMatrix} />}
      <GeneListsSection experiment={experiment} />
      {wasOptimized && (
        <>
          {experiment.crossValidation && (
            <CrossValidationSection cv={experiment.crossValidation} />
          )}
          {(experiment.enrichmentResults ?? []).length > 0 && (
            <EnrichmentSection results={experiment.enrichmentResults} />
          )}
          {experiment.optimizationResult && (
            <OptimizationSection result={experiment.optimizationResult} />
          )}
        </>
      )}
      {hasStepAnalysis && experiment.stepAnalysis && (
        <StepDecompositionSection stepAnalysis={experiment.stepAnalysis} />
      )}
      {!wasOptimized && !hasStepAnalysis && (
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-6 text-center">
          <Sparkles className="mx-auto mb-3 h-6 w-6 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">
            Analyze This Strategy
          </h3>
          <p className="mx-auto mt-1.5 max-w-md text-sm text-muted-foreground">
            Want to understand these results? Run step analysis to evaluate each step,
            compare operators, and find the best parameter settings.
          </p>
          <Button className="mt-4" size="sm" onClick={onOptimize}>
            <FlaskConical className="h-3.5 w-3.5" />
            Analyze This Strategy
          </Button>
        </div>
      )}
    </>
  );
}
