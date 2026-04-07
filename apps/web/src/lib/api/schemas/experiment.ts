/**
 * Zod schemas for Experiment API responses.
 *
 * Summary schemas match the flat shape from experiment_summary_to_json().
 * Detail schemas match the nested shape from experiment_to_json() (model_dump).
 */
import { z } from "zod";
import { DateTimeString } from "./common";

// ---------------------------------------------------------------------------
// Shared enums
// ---------------------------------------------------------------------------

const ExperimentStatusSchema = z.enum([
  "pending",
  "running",
  "completed",
  "error",
  "cancelled",
]);

const ExperimentModeSchema = z.enum(["single", "multi-step", "import"]);

// ---------------------------------------------------------------------------
// Experiment Summary (flat — from list endpoint)
// ---------------------------------------------------------------------------

export const ExperimentSummarySchema = z.object({
  id: z.string(),
  name: z.string(),
  siteId: z.string(),
  searchName: z.string(),
  recordType: z.string(),
  mode: ExperimentModeSchema,
  status: ExperimentStatusSchema,
  f1Score: z.number().nullable(),
  sensitivity: z.number().nullable(),
  specificity: z.number().nullable(),
  totalPositives: z.number(),
  totalNegatives: z.number(),
  createdAt: DateTimeString,
  batchId: z.string().nullable().optional(),
  benchmarkId: z.string().nullable().optional(),
  controlSetLabel: z.string().nullable().optional(),
  isPrimaryBenchmark: z.boolean(),
});

export const ExperimentSummaryListSchema = z.array(ExperimentSummarySchema);

// ---------------------------------------------------------------------------
// Full Experiment (nested — from detail endpoint)
// ---------------------------------------------------------------------------

// -- Config (nested under experiment.config) --------------------------------

const ExperimentConfigSchema = z.object({
  siteId: z.string(),
  recordType: z.string(),
  searchName: z.string(),
  parameters: z.record(z.string(), z.unknown()),
  positiveControls: z.array(z.string()),
  negativeControls: z.array(z.string()),
  controlsSearchName: z.string(),
  controlsParamName: z.string(),
  controlsValueFormat: z.enum(["newline", "json_list", "comma"]),
  enableCrossValidation: z.boolean(),
  kFolds: z.number(),
  enrichmentTypes: z.array(z.string()).optional(),
  name: z.string(),
  description: z.string(),
  mode: ExperimentModeSchema,
  optimizationSpecs: z.array(z.record(z.string(), z.unknown())).nullable().optional(),
  optimizationBudget: z.number().optional(),
  optimizationObjective: z.string().optional(),
  parameterDisplayValues: z.record(z.string(), z.string()).nullable().optional(),
  stepTree: z.unknown().optional(),
  sourceStrategyId: z.string().nullable().optional(),
  optimizationTargetStep: z.string().nullable().optional(),
  enableStepAnalysis: z.boolean().optional(),
  stepAnalysisPhases: z.array(z.string()).optional(),
  controlSetId: z.string().nullable().optional(),
  thresholdKnobs: z.array(z.record(z.string(), z.unknown())).nullable().optional(),
  operatorKnobs: z.array(z.record(z.string(), z.unknown())).nullable().optional(),
  treeOptimizationObjective: z.string().optional(),
  treeOptimizationBudget: z.number().optional(),
  maxListSize: z.number().nullable().optional(),
  sortAttribute: z.string().nullable().optional(),
  sortDirection: z.string().optional(),
  parentExperimentId: z.string().nullable().optional(),
  targetGeneIds: z.array(z.string()).nullable().optional(),
});

// -- Metrics (nested under experiment.metrics) ------------------------------

export const ConfusionMatrixSchema = z.object({
  truePositives: z.number(),
  falsePositives: z.number(),
  trueNegatives: z.number(),
  falseNegatives: z.number(),
});

export const ExperimentMetricsSchema = z.object({
  confusionMatrix: ConfusionMatrixSchema,
  sensitivity: z.number(),
  specificity: z.number(),
  precision: z.number(),
  f1Score: z.number(),
  mcc: z.number(),
  balancedAccuracy: z.number(),
  negativePredictiveValue: z.number(),
  falsePositiveRate: z.number(),
  falseNegativeRate: z.number(),
  youdensJ: z.number(),
  totalResults: z.number(),
  totalPositives: z.number(),
  totalNegatives: z.number(),
});

// -- Gene info --------------------------------------------------------------

const GeneInfoSchema = z.object({
  id: z.string(),
  name: z.string().nullable().optional(),
  organism: z.string().nullable().optional(),
  product: z.string().nullable().optional(),
});

// -- Enrichment -------------------------------------------------------------

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

const EnrichmentResultSchema = z.object({
  analysisType: z.string(),
  terms: z.array(EnrichmentTermSchema),
  totalGenesAnalyzed: z.number().default(0),
  backgroundSize: z.number().default(0),
  error: z.string().nullable().optional(),
});

// -- Cross-validation -------------------------------------------------------

const FoldMetricsSchema = z.object({
  foldIndex: z.number(),
  metrics: ExperimentMetricsSchema,
  positiveControlIds: z.array(z.string()).optional(),
  negativeControlIds: z.array(z.string()).optional(),
});

const CrossValidationResultSchema = z.object({
  k: z.number(),
  folds: z.array(FoldMetricsSchema),
  meanMetrics: ExperimentMetricsSchema,
  stdMetrics: z.record(z.string(), z.number()).optional(),
  overfittingScore: z.number().optional(),
  overfittingLevel: z.string().optional(),
});

// -- Rank metrics -----------------------------------------------------------

const RankMetricsSchema = z.object({
  precisionAtK: z.record(z.string(), z.number()).optional(),
  recallAtK: z.record(z.string(), z.number()).optional(),
  enrichmentAtK: z.record(z.string(), z.number()).optional(),
  prCurve: z.array(z.tuple([z.number(), z.number()])).optional(),
  listSizeVsRecall: z.array(z.tuple([z.number(), z.number()])).optional(),
  totalResults: z.number().optional(),
});

// -- Step analysis ----------------------------------------------------------

const StepAnalysisResultSchema = z.object({
  stepEvaluations: z.array(z.record(z.string(), z.unknown())).optional(),
  operatorComparisons: z.array(z.record(z.string(), z.unknown())).optional(),
  stepContributions: z.array(z.record(z.string(), z.unknown())).optional(),
  parameterSensitivities: z.array(z.record(z.string(), z.unknown())).optional(),
});

// -- Bootstrap/robustness ---------------------------------------------------

const BootstrapResultSchema = z.object({
  nIterations: z.number().optional(),
  metricCis: z.record(z.string(), z.record(z.string(), z.unknown())).optional(),
  rankMetricCis: z.record(z.string(), z.record(z.string(), z.unknown())).optional(),
  topKStability: z.number().optional(),
  negativeSetSensitivity: z.array(z.record(z.string(), z.unknown())).optional(),
});

// -- Tree optimization ------------------------------------------------------

const TreeOptimizationResultSchema = z.object({
  bestTrial: z.record(z.string(), z.unknown()).nullable().optional(),
  allTrials: z.array(z.record(z.string(), z.unknown())).optional(),
  totalTimeSeconds: z.number().optional(),
  objective: z.string().optional(),
});

// -- Full Experiment --------------------------------------------------------

export const ExperimentSchema = z.object({
  id: z.string(),
  config: ExperimentConfigSchema,
  userId: z.string().nullable().optional(),
  status: ExperimentStatusSchema,
  metrics: ExperimentMetricsSchema.nullable().optional(),
  crossValidation: CrossValidationResultSchema.nullable().optional(),
  enrichmentResults: z.array(EnrichmentResultSchema).optional(),
  truePositiveGenes: z.array(GeneInfoSchema).optional(),
  falseNegativeGenes: z.array(GeneInfoSchema).optional(),
  falsePositiveGenes: z.array(GeneInfoSchema).optional(),
  trueNegativeGenes: z.array(GeneInfoSchema).optional(),
  error: z.string().nullable().optional(),
  totalTimeSeconds: z.number().nullable().optional(),
  createdAt: DateTimeString,
  completedAt: DateTimeString.nullable().optional(),
  batchId: z.string().nullable().optional(),
  benchmarkId: z.string().nullable().optional(),
  controlSetLabel: z.string().nullable().optional(),
  isPrimaryBenchmark: z.boolean(),
  optimizationResult: z.record(z.string(), z.unknown()).nullable().optional(),
  wdkStrategyId: z.number().nullable().optional(),
  wdkStepId: z.number().nullable().optional(),
  notes: z.string().nullable().optional(),
  stepAnalysis: StepAnalysisResultSchema.nullable().optional(),
  rankMetrics: RankMetricsSchema.nullable().optional(),
  robustness: BootstrapResultSchema.nullable().optional(),
  treeOptimization: TreeOptimizationResultSchema.nullable().optional(),
});
