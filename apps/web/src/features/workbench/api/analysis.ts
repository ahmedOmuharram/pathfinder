import type { EnrichmentAnalysisType } from "@pathfinder/shared";
import { crossValidationResultResponseSchema } from "@pathfinder/shared/generated/zod/crossValidationResultResponseSchema";
import { enrichmentCompareResultSchema } from "@pathfinder/shared/generated/zod/enrichmentCompareResultSchema";
import { enrichmentResultResponseSchema } from "@pathfinder/shared/generated/zod/enrichmentResultResponseSchema";
import { overlapResultSchema } from "@pathfinder/shared/generated/zod/overlapResultSchema";
import type { CrossValidationResultResponse } from "@pathfinder/shared/generated/types/CrossValidationResultResponse";
import type { EnrichmentCompareResult } from "@pathfinder/shared/generated/types/EnrichmentCompareResult";
import type { EnrichmentResultResponse } from "@pathfinder/shared/generated/types/EnrichmentResultResponse";
import type { OverlapResult } from "@pathfinder/shared/generated/types/OverlapResult";
import { z } from "zod";

import { requestJson } from "@/lib/api/http";

const EnrichmentResultListSchema = z.array(enrichmentResultResponseSchema);

export type { OverlapResult, EnrichmentCompareResult };

export async function runCrossValidation(
  experimentId: string,
  kFolds: number,
): Promise<CrossValidationResultResponse> {
  return await requestJson(
    crossValidationResultResponseSchema,
    `/api/v1/experiments/${experimentId}/cross-validate`,
    { method: "POST", body: { kFolds } },
  );
}

export async function runEnrichment(
  experimentId: string,
  enrichmentTypes: EnrichmentAnalysisType[],
): Promise<EnrichmentResultResponse[]> {
  return await requestJson(
    EnrichmentResultListSchema,
    `/api/v1/experiments/${experimentId}/enrich`,
    { method: "POST", body: { enrichmentTypes } },
  );
}

export async function computeOverlap(
  experimentIds: string[],
  opts?: { orthologAware?: boolean },
): Promise<OverlapResult> {
  const query: Record<string, string> = {};
  if (opts?.orthologAware === true) query["orthologAware"] = "true";
  const hasQuery = Object.keys(query).length > 0;
  return await requestJson(overlapResultSchema, "/api/v1/experiments/overlap", {
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
    enrichmentCompareResultSchema,
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
