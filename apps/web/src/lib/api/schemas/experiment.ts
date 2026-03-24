/**
 * Zod schemas for Experiment API responses.
 *
 * All object schemas use .passthrough() so extra fields from the backend
 * are preserved rather than stripped.
 */
import { z } from "zod";
import { DateTimeString } from "./common";

// ---------------------------------------------------------------------------
// Experiment Summary
// ---------------------------------------------------------------------------

const ExperimentStatusSchema = z.enum([
  "pending",
  "running",
  "completed",
  "error",
  "cancelled",
]);

const ExperimentModeSchema = z.enum(["single", "multi-step", "import"]);

export const ExperimentSummarySchema = z.object({
  id: z.string(),
  name: z.string(),
  siteId: z.string(),
  searchName: z.string(),
  recordType: z.string(),
  mode: ExperimentModeSchema.optional(),
  status: ExperimentStatusSchema,
  f1Score: z.number().nullable(),
  sensitivity: z.number().nullable(),
  specificity: z.number().nullable(),
  totalPositives: z.number(),
  totalNegatives: z.number(),
  createdAt: DateTimeString,
  batchId: z.string().nullable(),
  benchmarkId: z.string().nullable(),
  controlSetLabel: z.string().nullable(),
  isPrimaryBenchmark: z.boolean(),
});

export const ExperimentSummaryListSchema = z.array(ExperimentSummarySchema);

// ---------------------------------------------------------------------------
// Full Experiment (detail endpoint)
// ---------------------------------------------------------------------------

const ClassifiedGeneSchema = z.object({
  id: z.string(),
  name: z.string().nullable().optional(),
});

const EnrichmentTermSchema = z.object({
  id: z.string(),
  name: z.string(),
  fdr: z.number(),
  pValue: z.number(),
  oddsRatio: z.number().nullable().optional(),
  genes: z.array(z.string()).nullable().optional(),
});

const EnrichmentResultDetailSchema = z.object({
  type: z.string(),
  terms: z.array(EnrichmentTermSchema),
});

export const ExperimentSchema = z.object({
  id: z.string(),
  name: z.string(),
  siteId: z.string(),
  searchName: z.string(),
  recordType: z.string(),
  mode: ExperimentModeSchema.optional(),
  status: ExperimentStatusSchema,
  f1Score: z.number().nullable(),
  sensitivity: z.number().nullable(),
  specificity: z.number().nullable(),
  totalPositives: z.number(),
  totalNegatives: z.number(),
  createdAt: DateTimeString,
  batchId: z.string().nullable(),
  benchmarkId: z.string().nullable(),
  controlSetLabel: z.string().nullable(),
  isPrimaryBenchmark: z.boolean(),
  notes: z.string().nullable().optional(),
  truePositiveGenes: z.array(ClassifiedGeneSchema).nullable().optional(),
  falsePositiveGenes: z.array(ClassifiedGeneSchema).nullable().optional(),
  trueNegativeGenes: z.array(ClassifiedGeneSchema).nullable().optional(),
  falseNegativeGenes: z.array(ClassifiedGeneSchema).nullable().optional(),
  enrichmentResults: z.array(EnrichmentResultDetailSchema).nullable().optional(),
});
