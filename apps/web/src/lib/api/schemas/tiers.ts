import { z } from "zod";
import { PipelinePhaseConfigSchema } from "./pipeline";

const TierPresetSchema = z.object({
  discovery: PipelinePhaseConfigSchema,
  planning: PipelinePhaseConfigSchema,
  execution: PipelinePhaseConfigSchema,
  verification: PipelinePhaseConfigSchema,
});

export const TierListResponseSchema = z.object({
  presets: z.record(z.string(), z.record(z.string(), TierPresetSchema)),
});

export type TierListResponse = z.infer<typeof TierListResponseSchema>;
export type TierPreset = z.infer<typeof TierPresetSchema>;
