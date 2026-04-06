import { z } from "zod";

/* ── Internal helper schemas ─────────────────────────────────────────── */

const OptimizationTrialSchema = z
  .object({
    trialNumber: z.number(),
    parameters: z.record(z.string(), z.unknown()).optional(),
    score: z.number(),
    recall: z.number().nullable().optional(),
    falsePositiveRate: z.number().nullable().optional(),
    estimatedSize: z.number().nullable().optional(),
    positiveHits: z.number().nullable().optional(),
    negativeHits: z.number().nullable().optional(),
    totalPositives: z.number().nullable().optional(),
    totalNegatives: z.number().nullable().optional(),
  })
  .passthrough();

const OptimizationParameterSpecSchema = z
  .object({
    name: z.string(),
    type: z.enum(["numeric", "integer", "categorical"]),
    minValue: z.number().nullable().optional(),
    maxValue: z.number().nullable().optional(),
    logScale: z.boolean().nullable().optional(),
    choices: z.array(z.string()).nullable().optional(),
  })
  .passthrough();

/* ── Exported Zod schemas ────────────────────────────────────────────── */

export const ToolCallStartDataSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    arguments: z.record(z.string(), z.unknown()).default({}),
  })
  .passthrough();

export const ToolCallEndDataSchema = z
  .object({
    id: z.string(),
    result: z.string().nullish(),
  })
  .passthrough();

export const OptimizationProgressDataSchema = z
  .object({
    optimizationId: z.string(),
    status: z.enum(["started", "running", "completed", "cancelled", "error"]),
    searchName: z.string().nullish(),
    recordType: z.string().nullish(),
    budget: z.number().nullish(),
    objective: z.string().nullish(),
    positiveControlsCount: z.number().nullish(),
    negativeControlsCount: z.number().nullish(),
    parameterSpecs: z.array(OptimizationParameterSpecSchema).nullish(),
    currentTrial: z.number().nullish(),
    totalTrials: z.number().nullish(),
    trial: OptimizationTrialSchema.nullish(),
    bestTrial: OptimizationTrialSchema.nullable().optional(),
    recentTrials: z.array(OptimizationTrialSchema).nullish(),
    allTrials: z.array(OptimizationTrialSchema).nullish(),
    paretoFrontier: z.array(OptimizationTrialSchema).nullish(),
    sensitivity: z.record(z.string(), z.number()).nullish(),
    totalTimeSeconds: z.number().nullish(),
    error: z.string().nullish(),
  })
  .passthrough();

export const ModelSelectedDataSchema = z
  .object({
    modelId: z.string(),
  })
  .passthrough();

export const ErrorDataSchema = z
  .object({
    error: z.string(),
  })
  .passthrough();

/* ── Zod schemas for previously unvalidated event types ───────────── */

const StrategyUpdateStepDataSchema = z
  .object({
    id: z.string(),
    kind: z.string().nullish(),
    displayName: z.string().nullish(),
    searchName: z.string().nullish(),
    operator: z.string().nullish(),
    primaryInputStepId: z.string().nullish(),
    secondaryInputStepId: z.string().nullish(),
    parameters: z.record(z.string(), z.unknown()).nullish(),
    estimatedSize: z.number().nullish(),
    wdkStepId: z.number().nullish(),
    isBuilt: z.boolean().optional(),
    isFiltered: z.boolean().optional(),
    recordType: z.string().nullish(),
    name: z.string().nullish(),
    description: z.string().nullish(),
    graphId: z.string().nullish(),
    graphName: z.string().nullish(),
  })
  .passthrough();

export const StrategyUpdateDataSchema = z
  .object({
    graphId: z.string().nullish(),
    step: StrategyUpdateStepDataSchema.nullish(),
  })
  .passthrough();

export const StrategyLinkDataSchema = z
  .object({
    graphId: z.string().nullish(),
    wdkStrategyId: z.number().nullish(),
    wdkUrl: z.string().nullish(),
    name: z.string().nullish(),
    description: z.string().nullish(),
    isSaved: z.boolean().nullish(),
  })
  .passthrough();

export const StrategyMetaDataSchema = z
  .object({
    graphId: z.string().nullish(),
    graphName: z.string().nullish(),
    name: z.string().nullish(),
    description: z.string().nullish(),
    recordType: z.string().nullable().optional(),
  })
  .passthrough();

export const GraphPlanDataSchema = z
  .object({
    graphId: z.string().nullish(),
    plan: z.unknown(),
    name: z.string().nullish(),
    recordType: z.string().nullish(),
    description: z.string().nullish(),
  })
  .passthrough();

const WorkbenchGeneSetInnerSchema = z
  .object({
    id: z.string().nullish(),
    name: z.string().nullish(),
    geneCount: z.number().nullish(),
    source: z.string().nullish(),
    siteId: z.string().nullish(),
  })
  .passthrough();

export const WorkbenchGeneSetDataSchema = z
  .object({
    geneSet: WorkbenchGeneSetInnerSchema.nullish(),
  })
  .passthrough();

export const PlanningThoughtDataSchema = z
  .object({
    thought: z.string(),
  })
  .passthrough();

export const PlanPresentedDataSchema = z
  .object({
    plan: z.record(z.string(), z.unknown()),
  })
  .passthrough();

export const PlanUpdatedDataSchema = z
  .object({
    planId: z.string(),
    updates: z.record(z.string(), z.unknown()),
  })
  .passthrough();

export const DecisionPresentedDataSchema = z
  .object({
    decisionId: z.string(),
    question: z.string(),
    options: z.array(z.record(z.string(), z.unknown())),
    context: z.string(),
    recommendation: z.string().nullable(),
  })
  .passthrough();

export const PhaseChangeDataSchema = z
  .object({
    phase: z.enum(["discovery", "planning", "execution", "verification", "completed"]),
    status: z.enum(["started", "completed", "failed", "awaiting_approval"]),
    validationError: z.string().nullable().optional(),
  })
  .passthrough();
