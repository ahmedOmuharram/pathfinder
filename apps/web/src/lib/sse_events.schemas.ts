import { z } from "zod";

/* ── Internal helper schemas ─────────────────────────────────────────── */

const OptimizationTrialSchema = z.looseObject({
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
});

const OptimizationParameterSpecSchema = z.looseObject({
  name: z.string(),
  type: z.enum(["numeric", "integer", "categorical"]),
  minValue: z.number().nullable().optional(),
  maxValue: z.number().nullable().optional(),
  logScale: z.boolean().nullable().optional(),
  choices: z.array(z.string()).nullable().optional(),
});

export const ClarificationQuestionSchema = z.looseObject({
  question: z.string(),
  context: z.string().optional(),
  field: z.string().nullable().optional(),
  priority: z.enum(["blocking", "optional"]).optional(),
  options: z.array(z.string()).optional(),
});

export const ResearchNoteSchema = z.looseObject({
  source: z.string(),
  finding: z.string(),
  url: z.string().nullable().optional(),
  citationId: z.string().nullable().optional(),
});

export const ProblemFrameSchema = z.looseObject({
  userGoal: z.string(),
  interpretedGoal: z.string(),
  organismScope: z.string().nullable().optional(),
  recordType: z.string().nullable().optional(),
  biologicalEntities: z.array(z.string()).optional(),
  inclusionCriteria: z.array(z.string()).optional(),
  exclusionCriteria: z.array(z.string()).optional(),
  likelyDataSources: z.array(z.string()).optional(),
  successCriteria: z.array(z.string()).optional(),
  assumptions: z.array(z.string()).optional(),
  blockingQuestions: z.array(ClarificationQuestionSchema).optional(),
  optionalQuestions: z.array(ClarificationQuestionSchema).optional(),
  researchNotes: z.array(ResearchNoteSchema).optional(),
  readyForWdkDiscovery: z.boolean(),
  confidence: z.number(),
});

export const ProblemFrameDataSchema = z.looseObject({
  problemFrame: ProblemFrameSchema,
});

/* ── Exported Zod schemas ────────────────────────────────────────────── */

export const ToolCallStartDataSchema = z.looseObject({
  id: z.string(),
  name: z.string(),
  arguments: z.record(z.string(), z.unknown()).default({}),
});

export const ToolCallEndDataSchema = z.looseObject({
  id: z.string(),
  result: z.string().nullish(),
});

export const OptimizationProgressDataSchema = z.looseObject({
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
});

export const ModelSelectedDataSchema = z.looseObject({
  pipeline: z.object({
    scoping: z.object({ modelId: z.string(), reasoningEffort: z.string() }),
    discovery: z.object({ modelId: z.string(), reasoningEffort: z.string() }),
    planning: z.object({ modelId: z.string(), reasoningEffort: z.string() }),
    execution: z.object({ modelId: z.string(), reasoningEffort: z.string() }),
    verification: z.object({ modelId: z.string(), reasoningEffort: z.string() }),
  }),
});

export const ErrorDataSchema = z.looseObject({
  error: z.string(),
});

/* ── Zod schemas for previously unvalidated event types ───────────── */

const StrategyUpdateStepDataSchema = z.looseObject({
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
});

export const StrategyUpdateDataSchema = z.looseObject({
  graphId: z.string().nullish(),
  step: StrategyUpdateStepDataSchema.nullish(),
});

export const StrategyLinkDataSchema = z.looseObject({
  graphId: z.string().nullish(),
  wdkStrategyId: z.number().nullish(),
  wdkUrl: z.string().nullish(),
  name: z.string().nullish(),
  description: z.string().nullish(),
  isSaved: z.boolean().nullish(),
});

export const StrategyMetaDataSchema = z.looseObject({
  graphId: z.string().nullish(),
  graphName: z.string().nullish(),
  name: z.string().nullish(),
  description: z.string().nullish(),
  recordType: z.string().nullable().optional(),
});

export const GraphPlanDataSchema = z.looseObject({
  graphId: z.string().nullish(),
  plan: z.unknown(),
  name: z.string().nullish(),
  recordType: z.string().nullish(),
  description: z.string().nullish(),
});

const WorkbenchGeneSetInnerSchema = z.looseObject({
  id: z.string().nullish(),
  name: z.string().nullish(),
  geneCount: z.number().nullish(),
  source: z.string().nullish(),
  siteId: z.string().nullish(),
});

export const WorkbenchGeneSetDataSchema = z.looseObject({
  geneSet: WorkbenchGeneSetInnerSchema.nullish(),
});

export const PlanningThoughtDataSchema = z.looseObject({
  thought: z.string(),
});

export const PlanPresentedDataSchema = z.looseObject({
  plan: z.record(z.string(), z.unknown()),
});

export const PlanApprovedDataSchema = z.looseObject({
  planId: z.string(),
  plan: z.record(z.string(), z.unknown()),
});

export const PlanUpdatedDataSchema = z.looseObject({
  planId: z.string(),
  updates: z.record(z.string(), z.unknown()),
});

export const DecisionPresentedDataSchema = z.looseObject({
  decisionId: z.string(),
  question: z.string(),
  options: z.array(z.record(z.string(), z.unknown())),
  context: z.string(),
  recommendation: z.string().nullable(),
});

export const PhaseChangeDataSchema = z.looseObject({
  phase: z.enum(["scoping", "discovery", "planning", "execution", "verification", "completed"]),
  status: z.enum(["started", "completed", "failed", "awaiting_approval", "awaiting_input"]),
  messageId: z.string().nullish(),
  messageGroupId: z.string().nullish(),
  emittedAt: z.string().nullish(),
  phaseStartedAt: z.string().nullish(),
  phaseCompletedAt: z.string().nullish(),
  durationMs: z.number().int().nullable().optional(),
  validationError: z.string().nullable().optional(),
});
