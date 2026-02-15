/**
 * Zod runtime validators for Pathfinder API payloads
 */

import { z } from "zod";

// Combine Operations

export const CombineOperatorSchema = z.enum([
  "INTERSECT",
  "UNION",
  "MINUS_LEFT",
  "MINUS_RIGHT",
  "COLOCATE",
]);

// Strategy Plan DSL (AST)

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
        parameters: z.record(z.string(), z.unknown()).optional(),
        customName: z.string().optional(),
      })
    )
    .optional(),
  reports: z
    .array(
      z.object({
        reportName: z.string(),
        config: z.record(z.string(), z.unknown()).optional(),
      })
    )
    .optional(),
});

// Recursive schema (untyped plan tree): avoid explicit `z.ZodType<...>` annotations here,
// because TypeScript treats them as self-referential and errors on circular types.
export const PlanStepNodeSchema: z.ZodTypeAny = BasePlanNodeSchema.extend({
  searchName: z.string().min(1),
  parameters: z.record(z.string(), z.unknown()).optional().default({}),
  primaryInput: z.lazy(() => PlanStepNodeSchema).optional(),
  secondaryInput: z.lazy(() => PlanStepNodeSchema).optional(),
  operator: CombineOperatorSchema.optional(),
  colocationParams: ColocationParamsSchema.optional(),
})
  .superRefine((node, ctx) => {
    const hasPrimary = node.primaryInput != null;
    const hasSecondary = node.secondaryInput != null;

    if (hasSecondary && !hasPrimary) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "secondaryInput requires primaryInput",
        path: ["secondaryInput"],
      });
    }

    if (hasSecondary && !node.operator) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "operator is required when secondaryInput is present",
        path: ["operator"],
      });
    }

    if (node.operator === "COLOCATE" && !node.colocationParams) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "colocationParams is required when operator is COLOCATE",
        path: ["colocationParams"],
      });
    }

    if (node.operator !== "COLOCATE" && node.colocationParams != null) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "colocationParams is only allowed when operator is COLOCATE",
        path: ["colocationParams"],
      });
    }
  });

export const StrategyPlanSchema = z.object({
  recordType: z.string(),
  root: PlanStepNodeSchema,
  metadata: z
    .object({
      name: z.string().optional(),
      description: z.string().optional(),
      siteId: z.string().optional(),
      createdAt: z.string().datetime().optional(),
    })
    .optional(),
});

// API Request/Response Schemas

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

// Search Schemas (site discovery)

export const SearchSchema = z.object({
  name: z.string(),
  displayName: z.string(),
  description: z.string().optional(),
  recordType: z.string(),
});

// Validation Helpers

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

