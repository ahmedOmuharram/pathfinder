/**
 * Shared analysis API types and functions -- used by both workbench and analysis features.
 */

import { requestJson } from "@/lib/api/http";
import { CustomEnrichmentResultSchema } from "./schemas/analysis";

// ---------------------------------------------------------------------------
// Custom Enrichment
// ---------------------------------------------------------------------------

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
  return (await requestJson(
    CustomEnrichmentResultSchema,
    `/api/v1/experiments/${experimentId}/custom-enrich`,
    { method: "POST", body: { geneSetName, geneIds } },
  )) as CustomEnrichmentResult;
}

// ---------------------------------------------------------------------------
// Threshold Sweep
// ---------------------------------------------------------------------------

export interface ThresholdSweepPoint {
  value: number | string;
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
  sweepType?: "numeric" | "categorical";
  points: ThresholdSweepPoint[];
}

export interface NumericSweepRequest {
  sweepType: "numeric";
  parameterName: string;
  minValue: number;
  maxValue: number;
  steps: number;
}

export interface CategoricalSweepRequest {
  sweepType: "categorical";
  parameterName: string;
  values: string[];
}

export type SweepRequest = NumericSweepRequest | CategoricalSweepRequest;

interface ThresholdSweepProgress {
  point: ThresholdSweepPoint;
  completedCount: number;
  totalCount: number;
}

interface ThresholdSweepCallbacks {
  onPoint: (progress: ThresholdSweepProgress) => void;
  onComplete: (result: ThresholdSweepResult) => void;
  onError: (error: Error) => void;
}

export async function streamThresholdSweep(
  experimentId: string,
  request: SweepRequest,
  callbacks: ThresholdSweepCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const { streamSSEParsed } = await import("@/lib/sse");

  await streamSSEParsed<ThresholdSweepProgress | ThresholdSweepResult>(
    `/api/v1/experiments/${experimentId}/threshold-sweep`,
    {
      method: "POST",
      body: request,
      ...(signal != null ? { signal } : {}),
    },
    {
      onFrame: ({ event, data }) => {
        if (event === "sweep_point") {
          callbacks.onPoint(data as ThresholdSweepProgress);
        } else if (event === "sweep_complete") {
          callbacks.onComplete(data as ThresholdSweepResult);
        }
      },
      onError: callbacks.onError,
      readTimeoutMs: 5 * 60 * 1000,
    },
  );
}
