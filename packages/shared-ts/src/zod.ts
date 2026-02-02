/**
 * Zod runtime validators for Pathfinder API payloads
 */

import { z } from "zod";

// ============================================================================
// Combine Operations
// ============================================================================

export const CombineOperatorSchema = z.enum([
  "INTERSECT",
  "UNION",
  "MINUS_LEFT",
  "MINUS_RIGHT",
  "COLOCATE",
]);

// ============================================================================
// Strategy Plan DSL (AST)
// ============================================================================

export const ColocationParamsSchema = z.object({
  upstream: z.number().int().min(0),
  downstream: z.number().int().min(0),
  strand: z.enum(["same", "opposite", "both"]).default("both"),
});

const BasePlanNodeSchema = z.object({
  id: z.string().optional(),
  displayName: z.string().optional(),
  filters: z
    .array(
      z.object({
        name: z.string(),
        value: z.unknown(),
        disabled: z.boolean().optional(),
      })
    )
    .optional(),
  analyses: z
    .array(
      z.object({
        analysisType: z.string(),
        parameters: z.record(z.unknown()).optional(),
        customName: z.string().optional(),
      })
    )
    .optional(),
  reports: z
    .array(
      z.object({
        reportName: z.string(),
        config: z.record(z.unknown()).optional(),
      })
    )
    .optional(),
});

export const SearchNodeSchema = BasePlanNodeSchema.extend({
  type: z.literal("search"),
  searchName: z.string(),
  parameters: z.record(z.unknown()),
});

// Recursive schemas: avoid explicit `z.ZodType<...>` annotations here, because
// TypeScript treats them as self-referential and errors on circular types.
export const CombineNodeSchema: z.AnyZodObject = BasePlanNodeSchema.extend({
  type: z.literal("combine"),
  operator: CombineOperatorSchema,
  left: z.lazy(() => PlanNodeSchema),
  right: z.lazy(() => PlanNodeSchema),
  colocationParams: ColocationParamsSchema.optional(),
}) as z.AnyZodObject;

export const TransformNodeSchema: z.AnyZodObject = BasePlanNodeSchema.extend({
  type: z.literal("transform"),
  transformName: z.string(),
  input: z.lazy(() => PlanNodeSchema),
  parameters: z.record(z.unknown()).optional(),
}) as z.AnyZodObject;

export const PlanNodeSchema: z.ZodTypeAny = z.discriminatedUnion("type", [
  SearchNodeSchema,
  CombineNodeSchema,
  TransformNodeSchema,
]);

export const StrategyPlanSchema = z.object({
  recordType: z.string(),
  root: PlanNodeSchema,
  metadata: z
    .object({
      name: z.string().optional(),
      description: z.string().optional(),
      siteId: z.string().optional(),
      createdAt: z.string().datetime().optional(),
    })
    .optional(),
});

// ============================================================================
// API Request/Response Schemas
// ============================================================================

export const ChatRequestSchema = z.object({
  strategyId: z.string().uuid().optional(),
  siteId: z.string(),
  message: z.string().min(1).max(10000),
});

export const PreviewRequestSchema = z.object({
  strategyId: z.string().uuid(),
  stepId: z.string(),
  limit: z.number().int().min(1).max(1000).default(100),
});

export const DownloadRequestSchema = z.object({
  strategyId: z.string().uuid(),
  stepId: z.string(),
  format: z.enum(["csv", "json", "tab"]).default("csv"),
  attributes: z.array(z.string()).optional(),
});

export const CreateStrategyRequestSchema = z.object({
  name: z.string().min(1).max(255),
  siteId: z.string(),
  plan: StrategyPlanSchema,
});

export const UpdateStrategyRequestSchema = z.object({
  name: z.string().min(1).max(255).optional(),
  plan: StrategyPlanSchema.optional(),
});

// ============================================================================
// Search Schemas (site discovery)
// ============================================================================

export const SearchSchema = z.object({
  name: z.string(),
  displayName: z.string(),
  description: z.string().optional(),
  recordType: z.string(),
});

// ============================================================================
// Validation Helpers
// ============================================================================

export function validateChatRequest(data: unknown) {
  return ChatRequestSchema.safeParse(data);
}

export function validateStrategyPlan(data: unknown) {
  return StrategyPlanSchema.safeParse(data);
}

export function validateCreateStrategyRequest(data: unknown) {
  return CreateStrategyRequestSchema.safeParse(data);
}

export function validatePreviewRequest(data: unknown) {
  return PreviewRequestSchema.safeParse(data);
}

export function validateDownloadRequest(data: unknown) {
  return DownloadRequestSchema.safeParse(data);
}

