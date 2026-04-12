import { z } from "zod";

export const PipelinePhaseConfigSchema = z.object({
  modelId: z.string(),
  reasoningEffort: z.enum(["none", "low", "medium", "high"]),
});

export const PipelineConfigSchema = z.object({
  scoping: PipelinePhaseConfigSchema,
  discovery: PipelinePhaseConfigSchema,
  planning: PipelinePhaseConfigSchema,
  execution: PipelinePhaseConfigSchema,
  verification: PipelinePhaseConfigSchema,
});
