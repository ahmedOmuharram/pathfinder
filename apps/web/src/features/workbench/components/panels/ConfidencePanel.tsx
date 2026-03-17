"use client";

import { useMemo } from "react";
import { ShieldCheck } from "lucide-react";
import type { Experiment, GeneInfo, EnrichmentResult } from "@pathfinder/shared";
import { AnalysisPanelContainer } from "../AnalysisPanelContainer";
import { useWorkbenchStore } from "../../store";

// ---------------------------------------------------------------------------
// Pure computation — gene confidence scoring
// ---------------------------------------------------------------------------

interface GeneConfidenceScore {
  geneId: string;
  compositeScore: number;
  classificationScore: number;
  enrichmentScore: number;
}

const CLASSIFICATION_WEIGHTS = {
  TP: 1.0,
  FP: -1.0,
  FN: -0.5,
  TN: 0.0,
} as const;

function computeEnrichmentGeneCounts(enrichmentResults: EnrichmentResult[]): {
  counts: Map<string, number>;
  maxTerms: number;
} {
  const counts = new Map<string, number>();
  let maxTerms = 0;
  for (const result of enrichmentResults) {
    for (const term of result.terms) {
      if (term.fdr <= 0.05) {
        maxTerms++;
        for (const geneId of term.genes ?? []) {
          counts.set(geneId, (counts.get(geneId) ?? 0) + 1);
        }
      }
    }
  }
  return { counts, maxTerms };
}

function computeConfidenceScores(experiment: Experiment): GeneConfidenceScore[] {
  const classified: [string, number][] = [];
  const seen = new Set<string>();

  const lists: [keyof typeof CLASSIFICATION_WEIGHTS, GeneInfo[]][] = [
    ["TP", experiment.truePositiveGenes ?? []],
    ["FP", experiment.falsePositiveGenes ?? []],
    ["FN", experiment.falseNegativeGenes ?? []],
    ["TN", experiment.trueNegativeGenes ?? []],
  ];

  for (const [label, genes] of lists) {
    for (const gene of genes) {
      if (!seen.has(gene.id)) {
        seen.add(gene.id);
        classified.push([gene.id, CLASSIFICATION_WEIGHTS[label]]);
      }
    }
  }

  // Enrichment support: count how many significant terms contain each gene
  const { counts: enrichCounts, maxTerms } = computeEnrichmentGeneCounts(
    experiment.enrichmentResults ?? [],
  );
  const maxTermsDenom = Math.max(maxTerms, 1);

  const results: GeneConfidenceScore[] = classified.map(([geneId, clsScore]) => {
    const enrScore = Math.min((enrichCounts.get(geneId) ?? 0) / maxTermsDenom, 1.0);
    const composite = (clsScore + enrScore) / 2.0;
    return {
      geneId,
      compositeScore: composite,
      classificationScore: clsScore,
      enrichmentScore: enrScore,
    };
  });

  results.sort((a, b) => b.compositeScore - a.compositeScore);
  return results;
}

// ---------------------------------------------------------------------------
// Score color helper
// ---------------------------------------------------------------------------

function scoreColor(value: number): string {
  if (value > 0.15) return "text-green-600 dark:text-green-400";
  if (value < -0.15) return "text-red-600 dark:text-red-400";
  return "text-muted-foreground";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function hasClassifiedGenes(exp: Experiment): boolean {
  return (
    (exp.truePositiveGenes?.length ?? 0) > 0 ||
    (exp.falsePositiveGenes?.length ?? 0) > 0 ||
    (exp.falseNegativeGenes?.length ?? 0) > 0 ||
    (exp.trueNegativeGenes?.length ?? 0) > 0
  );
}

export function ConfidencePanel() {
  const activeSetId = useWorkbenchStore((s) => s.activeSetId);
  const lastExperiment = useWorkbenchStore((s) => s.lastExperiment);
  const lastExperimentSetId = useWorkbenchStore((s) => s.lastExperimentSetId);

  const isRelevant =
    lastExperiment &&
    lastExperimentSetId === activeSetId &&
    hasClassifiedGenes(lastExperiment);

  const scores = useMemo(
    () => (isRelevant ? computeConfidenceScores(lastExperiment) : []),
    [isRelevant, lastExperiment],
  );

  return (
    <AnalysisPanelContainer
      panelId="confidence"
      title="Gene Confidence"
      subtitle="Per-gene composite confidence ranking"
      icon={<ShieldCheck className="h-4 w-4" />}
      disabled={!isRelevant}
      disabledReason="Requires an experiment with classified genes"
    >
      <div className="max-h-96 overflow-auto">
        <table role="table" className="w-full text-xs">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="pb-1.5 pr-3 font-medium">Gene ID</th>
              <th className="pb-1.5 pr-3 font-medium">Composite</th>
              <th className="pb-1.5 pr-3 font-medium">Classification</th>
              <th className="pb-1.5 font-medium">Enrichment</th>
            </tr>
          </thead>
          <tbody>
            {scores.map((s) => (
              <tr key={s.geneId} className="border-b border-border/50">
                <td className="py-1 pr-3 font-mono">{s.geneId}</td>
                <td className={`py-1 pr-3 ${scoreColor(s.compositeScore)}`}>
                  {s.compositeScore.toFixed(3)}
                </td>
                <td className={`py-1 pr-3 ${scoreColor(s.classificationScore)}`}>
                  {s.classificationScore.toFixed(1)}
                </td>
                <td className={`py-1 ${scoreColor(s.enrichmentScore)}`}>
                  {s.enrichmentScore.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AnalysisPanelContainer>
  );
}
