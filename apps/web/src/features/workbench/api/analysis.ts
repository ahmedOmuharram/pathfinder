import type { EnrichmentAnalysisType } from "@pathfinder/shared";
import { requestJson } from "@/lib/api/http";
import {
  CrossValidationResultSchema,
  EnrichmentResultListSchema,
  OverlapResultSchema,
  EnrichmentCompareResultSchema,
} from "@/lib/api/schemas/analysis";
import type { z } from "zod";

export type OverlapResult = z.infer<typeof OverlapResultSchema>;
export type EnrichmentCompareResult = z.infer<typeof EnrichmentCompareResultSchema>;

export async function runCrossValidation(
  experimentId: string,
  kFolds: number,
): Promise<z.infer<typeof CrossValidationResultSchema>> {
  return await requestJson(CrossValidationResultSchema, `/api/v1/experiments/${experimentId}/cross-validate`, {
    method: "POST",
    body: { kFolds },
  });
}

export async function runEnrichment(
  experimentId: string,
  enrichmentTypes: EnrichmentAnalysisType[],
): Promise<z.infer<typeof EnrichmentResultListSchema>> {
  return await requestJson(EnrichmentResultListSchema, `/api/v1/experiments/${experimentId}/enrich`, {
    method: "POST",
    body: { enrichmentTypes },
  });
}

export async function computeOverlap(
  experimentIds: string[],
  opts?: { orthologAware?: boolean },
): Promise<OverlapResult> {
  const query: Record<string, string> = {};
  if (opts?.orthologAware === true) query["orthologAware"] = "true";
  const hasQuery = Object.keys(query).length > 0;
  return await requestJson(OverlapResultSchema, "/api/v1/experiments/overlap", {
    method: "POST",
    body: { experimentIds },
    ...(hasQuery ? { query } : {}),
  });
}

export async function compareEnrichment(
  experimentIds: string[],
  analysisType?: string,
): Promise<EnrichmentCompareResult> {
  return await requestJson(
    EnrichmentCompareResultSchema,
    "/api/v1/experiments/enrichment-compare",
    {
      method: "POST",
      body: {
        experimentIds,
        ...(analysisType != null && analysisType !== "" ? { analysisType } : {}),
      },
    },
  );
}
