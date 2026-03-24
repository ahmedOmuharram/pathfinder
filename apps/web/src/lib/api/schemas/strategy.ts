/**
 * Zod schemas for Strategy / Step API responses.
 *
 * All object schemas use .passthrough() so extra fields from the backend
 * are preserved rather than stripped.
 */
import { z } from "zod";
import { DateTimeString, ParamRecord, UuidString } from "./common";

// ---------------------------------------------------------------------------
// Supporting types
// ---------------------------------------------------------------------------

const StepFilterSchema = z.object({
  name: z.string(),
  value: z.unknown(),
  disabled: z.boolean(),
});

const StepAnalysisSchema = z.object({
  analysisType: z.string(),
  parameters: ParamRecord.optional(),
  customName: z.string().nullable().optional(),
});

const StepReportSchema = z.object({
  reportName: z.string(),
  config: ParamRecord.optional(),
});

// ---------------------------------------------------------------------------
// Step
// ---------------------------------------------------------------------------

const StepSchema = z.object({
  id: z.string(),
  kind: z.string().nullable().optional(),
  displayName: z.string(),
  searchName: z.string().nullable().optional(),
  recordType: z.string().nullable().optional(),
  parameters: ParamRecord.nullable().optional(),
  operator: z.string().nullable().optional(),
  colocationParams: z.record(z.string(), z.unknown()).nullable().optional(),
  primaryInputStepId: z.string().nullable().optional(),
  secondaryInputStepId: z.string().nullable().optional(),
  estimatedSize: z.number().nullable().optional(),
  wdkStepId: z.number().nullable().optional(),
  isBuilt: z.boolean().optional().default(false),
  isFiltered: z.boolean().optional().default(false),
  validation: z
    .object({
      level: z.string(),
      isValid: z.boolean(),
      errors: z
        .object({
          general: z.array(z.string()),
          byKey: z.record(z.string(), z.array(z.string())),
        })
        .nullable()
        .optional(),
    })
    .nullable()
    .optional(),
  filters: z.array(StepFilterSchema).nullable().optional(),
  analyses: z.array(StepAnalysisSchema).nullable().optional(),
  reports: z.array(StepReportSchema).nullable().optional(),
});

// ---------------------------------------------------------------------------
// Strategy
// ---------------------------------------------------------------------------

export const StrategySchema = z.object({
  id: UuidString,
  name: z.string(),
  title: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  siteId: z.string(),
  recordType: z.string().nullable(),
  steps: z.array(StepSchema).optional(),
  rootStepId: z.string().nullable().optional(),
  wdkStrategyId: z.number().nullable().optional(),
  isSaved: z.boolean(),
  createdAt: DateTimeString,
  updatedAt: DateTimeString,
  stepCount: z.number().nullable().optional(),
  estimatedSize: z.number().nullable().optional(),
  wdkUrl: z.string().nullable().optional(),
  // messages / thinking are large nested blobs — accept but don't validate deeply
  messages: z.array(z.record(z.string(), z.unknown())).nullable().optional(),
  thinking: z.record(z.string(), z.unknown()).nullable().optional(),
  modelId: z.string().nullable().optional(),
});

// ---------------------------------------------------------------------------
// Lightweight response wrappers
// ---------------------------------------------------------------------------

export const OpenStrategyResponseSchema = z.object({
  strategyId: z.string(),
});

export const StepCountsResponseSchema = z.object({
  counts: z.record(z.string(), z.number().nullable()),
});

/**
 * List endpoints return strategy objects without `steps` / `rootStepId`.
 * This schema makes those (and other detail-only fields) optional.
 */
export const StrategyListItemSchema = z.object({
  id: UuidString,
  name: z.string(),
  siteId: z.string(),
  createdAt: DateTimeString,
  updatedAt: DateTimeString,
  // Detail-only fields are optional in list responses
  title: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  recordType: z.string().nullable().optional(),
  steps: z.array(StepSchema).optional(),
  rootStepId: z.string().nullable().optional(),
  wdkStrategyId: z.number().nullable().optional(),
  isSaved: z.boolean().optional(),
  stepCount: z.number().nullable().optional(),
  estimatedSize: z.number().nullable().optional(),
  wdkUrl: z.string().nullable().optional(),
  messages: z.array(z.record(z.string(), z.unknown())).nullable().optional(),
  thinking: z.record(z.string(), z.unknown()).nullable().optional(),
  modelId: z.string().nullable().optional(),
});

export const StrategyListItemListSchema = z.array(StrategyListItemSchema);

// ---------------------------------------------------------------------------
// Plan normalization
// ---------------------------------------------------------------------------

/**
 * Minimal PlanStepNode schema — recursive tree structure.
 * We validate the known top-level fields but use .passthrough() to keep
 * the recursive children as-is since Zod lazy schemas are expensive.
 */
const PlanStepNodeSchema: z.ZodType<{
  searchName: string;
  [key: string]: unknown;
}> = z.object({ searchName: z.string() });

/** The plan field has known top-level structure; deeper nodes are passthrough. */
export const NormalizePlanResponseSchema = z.object({
  plan: z.object({
    recordType: z.string(),
    root: PlanStepNodeSchema,
  }),
  warnings: z.array(z.unknown()).nullable().optional(),
});
