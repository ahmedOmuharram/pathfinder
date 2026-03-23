"use client";

import { useEffect, useState } from "react";
import { Loader2, ShieldCheck } from "lucide-react";
import type {
  Experiment,
  EnrichmentResult,
  GeneConfidenceScore,
} from "@pathfinder/shared";
import { requestJson } from "@/lib/api/http";
import { AnalysisPanelContainer } from "../AnalysisPanelContainer";
import { useWorkbenchStore } from "../../store";

// ---------------------------------------------------------------------------
// Enrichment data extraction (prepares input for the backend)
// ---------------------------------------------------------------------------

function extractEnrichmentCounts(enrichmentResults: EnrichmentResult[]): {
  enrichmentGeneCounts: Record<string, number>;
  maxEnrichmentTerms: number;
} {
  const counts: Record<string, number> = {};
  let maxTerms = 0;
  for (const result of enrichmentResults) {
    for (const term of result.terms) {
      if (term.fdr <= 0.05) {
        maxTerms++;
        for (const geneId of term.genes ?? []) {
          counts[geneId] = (counts[geneId] ?? 0) + 1;
        }
      }
    }
  }
  return { enrichmentGeneCounts: counts, maxEnrichmentTerms: maxTerms };
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
    lastExperiment != null &&
    lastExperimentSetId === activeSetId &&
    hasClassifiedGenes(lastExperiment) === true;

  const [scores, setScores] = useState<GeneConfidenceScore[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (
      lastExperiment == null ||
      lastExperimentSetId !== activeSetId ||
      !hasClassifiedGenes(lastExperiment)
    ) {
      setScores([]);
      setError(null);
      return;
    }

    const experiment = lastExperiment;
    let cancelled = false;

    async function fetchScores() {
      setLoading(true);
      setError(null);

      const { enrichmentGeneCounts, maxEnrichmentTerms } = extractEnrichmentCounts(
        experiment.enrichmentResults ?? [],
      );

      try {
        const data = await requestJson<GeneConfidenceScore[]>(
          "/api/v1/gene-sets/confidence",
          {
            method: "POST",
            body: {
              tpIds: (experiment.truePositiveGenes ?? []).map((g) => g.id),
              fpIds: (experiment.falsePositiveGenes ?? []).map((g) => g.id),
              fnIds: (experiment.falseNegativeGenes ?? []).map((g) => g.id),
              tnIds: (experiment.trueNegativeGenes ?? []).map((g) => g.id),
              enrichmentGeneCounts:
                Object.keys(enrichmentGeneCounts).length > 0
                  ? enrichmentGeneCounts
                  : undefined,
              maxEnrichmentTerms,
            },
          },
        );
        if (!cancelled) setScores(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void fetchScores();
    return () => {
      cancelled = true;
    };
  }, [lastExperiment, lastExperimentSetId, activeSetId]);

  return (
    <AnalysisPanelContainer
      panelId="confidence"
      title="Gene Confidence"
      subtitle="Per-gene composite confidence ranking"
      icon={<ShieldCheck className="h-4 w-4" />}
      disabled={!isRelevant}
      disabledReason="Requires an experiment with classified genes"
    >
      {loading && (
        <div className="flex items-center gap-2 py-4 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Computing scores…
        </div>
      )}

      {error != null && <p className="text-xs text-destructive">{error}</p>}

      {!loading && error == null && scores.length > 0 && (
        <div className="max-h-96 overflow-auto">
          <table role="table" className="w-full text-xs">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="pb-1.5 pr-3 font-medium">Gene ID</th>
                <th className="pb-1.5 pr-3 font-medium">Composite</th>
                <th className="pb-1.5 pr-3 font-medium">Classification</th>
                <th className="pb-1.5 pr-3 font-medium">Ensemble</th>
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
                  <td className={`py-1 pr-3 ${scoreColor(s.ensembleScore)}`}>
                    {s.ensembleScore.toFixed(2)}
                  </td>
                  <td className={`py-1 ${scoreColor(s.enrichmentScore)}`}>
                    {s.enrichmentScore.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AnalysisPanelContainer>
  );
}
