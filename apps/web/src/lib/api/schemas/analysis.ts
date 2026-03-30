/**
 * Zod schemas for Analysis API responses.
 *
 * All object schemas use .passthrough() so extra fields from the backend
 * are preserved rather than stripped.
 */
import { z } from "zod";
import { ExperimentMetricsSchema } from "./experiment";

// ---------------------------------------------------------------------------
// Custom Enrichment
// ---------------------------------------------------------------------------

export const CustomEnrichmentResultSchema = z.object({
  geneSetName: z.string(),
  geneSetSize: z.number(),
  overlapCount: z.number(),
  overlapGenes: z.array(z.string()),
  backgroundSize: z.number(),
  tpCount: z.number(),
  foldEnrichment: z.number(),
  pValue: z.number(),
  oddsRatio: z.number(),
});

// ---------------------------------------------------------------------------
// Enrichment Result (shared across gene-set and experiment enrichment)
// ---------------------------------------------------------------------------

const EnrichmentTermSchema = z.object({
  termId: z.string(),
  termName: z.string(),
  geneCount: z.number(),
  backgroundCount: z.number(),
  foldEnrichment: z.number(),
  oddsRatio: z.number(),
  pValue: z.number(),
  fdr: z.number(),
  bonferroni: z.number(),
  genes: z.array(z.string()).optional(),
});

export const EnrichmentResultSchema = z.object({
  analysisType: z.string(),
  terms: z.array(EnrichmentTermSchema),
  totalGenesAnalyzed: z.number().default(0),
  backgroundSize: z.number().default(0),
  error: z.string().nullable().optional(),
});

export const EnrichmentResultListSchema = z.array(EnrichmentResultSchema);

// ---------------------------------------------------------------------------
// Cross-validation
// ---------------------------------------------------------------------------

const FoldMetricsSchema = z.object({
  foldIndex: z.number(),
  metrics: ExperimentMetricsSchema,
  positiveControlIds: z.array(z.string()).optional(),
  negativeControlIds: z.array(z.string()).optional(),
});

export const CrossValidationResultSchema = z.object({
  k: z.number(),
  folds: z.array(FoldMetricsSchema),
  meanMetrics: ExperimentMetricsSchema,
  stdMetrics: z.record(z.string(), z.number()).optional(),
  overfittingScore: z.number().optional(),
  overfittingLevel: z.string().optional(),
});

// ---------------------------------------------------------------------------
// Overlap
// ---------------------------------------------------------------------------

const OverlapPairSchema = z.object({
  experimentA: z.string(),
  experimentB: z.string(),
  labelA: z.string(),
  labelB: z.string(),
  sizeA: z.number(),
  sizeB: z.number(),
  intersection: z.number(),
  union: z.number(),
  jaccard: z.number(),
  sharedGenes: z.array(z.string()),
  uniqueA: z.array(z.string()),
  uniqueB: z.array(z.string()),
});

const PerExperimentOverlapSchema = z.object({
  experimentId: z.string(),
  label: z.string(),
  totalGenes: z.number(),
  uniqueGenes: z.number(),
  sharedGenes: z.number(),
});

const GeneMembershipSchema = z.object({
  geneId: z.string(),
  foundIn: z.number(),
  totalExperiments: z.number(),
  experiments: z.array(z.string()),
});

export const OverlapResultSchema = z.object({
  experimentIds: z.array(z.string()),
  experimentLabels: z.record(z.string(), z.string()),
  pairwise: z.array(OverlapPairSchema),
  perExperiment: z.array(PerExperimentOverlapSchema),
  universalGenes: z.array(z.string()),
  totalUniqueGenes: z.number(),
  geneMembership: z.array(GeneMembershipSchema),
});

// ---------------------------------------------------------------------------
// Enrichment compare
// ---------------------------------------------------------------------------

const EnrichmentCompareRowSchema = z.object({
  termKey: z.string(),
  termName: z.string(),
  analysisType: z.string(),
  scores: z.record(z.string(), z.number().nullable()),
  maxScore: z.number(),
  experimentCount: z.number(),
});

export const EnrichmentCompareResultSchema = z.object({
  experimentIds: z.array(z.string()),
  experimentLabels: z.record(z.string(), z.string()),
  rows: z.array(EnrichmentCompareRowSchema),
  totalTerms: z.number(),
});

// ---------------------------------------------------------------------------
// Refine experiment
// ---------------------------------------------------------------------------

export const RefineResponseSchema = z.object({
  success: z.boolean(),
  newStepId: z.number().optional(),
});
