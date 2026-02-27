import type {
  CrossValidationResult,
  EnrichmentAnalysisType,
  EnrichmentResult,
} from "@pathfinder/shared";
import { requestJson } from "@/lib/api/http";

export async function runCrossValidation(
  experimentId: string,
  kFolds: number,
): Promise<CrossValidationResult> {
  return await requestJson(`/api/v1/experiments/${experimentId}/cross-validate`, {
    method: "POST",
    body: { kFolds },
  });
}

export async function runEnrichment(
  experimentId: string,
  enrichmentTypes: EnrichmentAnalysisType[],
): Promise<EnrichmentResult[]> {
  return await requestJson(`/api/v1/experiments/${experimentId}/enrich`, {
    method: "POST",
    body: { enrichmentTypes },
  });
}

export interface OverlapResult {
  experimentIds: string[];
  experimentLabels: Record<string, string>;
  pairwise: {
    experimentA: string;
    experimentB: string;
    labelA: string;
    labelB: string;
    sizeA: number;
    sizeB: number;
    intersection: number;
    union: number;
    jaccard: number;
    sharedGenes: string[];
    uniqueA: string[];
    uniqueB: string[];
  }[];
  perExperiment: {
    experimentId: string;
    label: string;
    totalGenes: number;
    uniqueGenes: number;
    sharedGenes: number;
  }[];
  universalGenes: string[];
  totalUniqueGenes: number;
  geneMembership: {
    geneId: string;
    foundIn: number;
    totalExperiments: number;
    experiments: string[];
  }[];
}

export async function computeOverlap(
  experimentIds: string[],
  opts?: { orthologAware?: boolean },
): Promise<OverlapResult> {
  const query: Record<string, string> = {};
  if (opts?.orthologAware) query.orthologAware = "true";
  return await requestJson<OverlapResult>("/api/v1/experiments/overlap", {
    method: "POST",
    body: { experimentIds },
    query: Object.keys(query).length > 0 ? query : undefined,
  });
}

export interface EnrichmentCompareResult {
  experimentIds: string[];
  experimentLabels: Record<string, string>;
  rows: {
    termKey: string;
    termName: string;
    analysisType: string;
    scores: Record<string, number | null>;
    maxScore: number;
    experimentCount: number;
  }[];
  totalTerms: number;
}

export async function compareEnrichment(
  experimentIds: string[],
  analysisType?: string,
): Promise<EnrichmentCompareResult> {
  return await requestJson<EnrichmentCompareResult>(
    "/api/v1/experiments/enrichment-compare",
    {
      method: "POST",
      body: { experimentIds, ...(analysisType ? { analysisType } : {}) },
    },
  );
}

export interface CustomEnrichmentResult {
  geneSetName: string;
  geneSetSize: number;
  overlapCount: number;
  overlapGenes: string[];
  backgroundSize: number;
  tpCount: number;
  foldEnrichment: number;
  pValue: number;
  oddsRatio: number;
}

export async function runCustomEnrichment(
  experimentId: string,
  geneSetName: string,
  geneIds: string[],
): Promise<CustomEnrichmentResult> {
  return await requestJson<CustomEnrichmentResult>(
    `/api/v1/experiments/${experimentId}/custom-enrich`,
    { method: "POST", body: { geneSetName, geneIds } },
  );
}

export interface ThresholdSweepPoint {
  value: number;
  metrics: {
    sensitivity: number;
    specificity: number;
    precision: number;
    f1Score: number;
    mcc: number;
    balancedAccuracy: number;
    totalResults: number;
    falsePositiveRate: number;
  } | null;
  error?: string;
}

export interface ThresholdSweepResult {
  parameter: string;
  points: ThresholdSweepPoint[];
}

/** Default timeout for threshold-sweep (5 min). Sweep runs many WDK steps and can be slow. */
const THRESHOLD_SWEEP_TIMEOUT_MS = 5 * 60 * 1000;

export async function runThresholdSweep(
  experimentId: string,
  parameterName: string,
  minValue: number,
  maxValue: number,
  steps: number = 10,
): Promise<ThresholdSweepResult> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(
    () => controller.abort(),
    THRESHOLD_SWEEP_TIMEOUT_MS,
  );
  try {
    return await requestJson<ThresholdSweepResult>(
      `/api/v1/experiments/${experimentId}/threshold-sweep`,
      {
        method: "POST",
        body: { parameterName, minValue, maxValue, steps },
        signal: controller.signal,
      },
    );
  } finally {
    window.clearTimeout(timeoutId);
  }
}
