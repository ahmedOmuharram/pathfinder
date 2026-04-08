/**
 * Zod schemas for ensemble scoring responses.
 *
 */
import { z } from "zod";

export const EnsembleScoreSchema = z.object({
  geneId: z.string(),
  frequency: z.number(),
  count: z.number(),
  total: z.number(),
  inPositives: z.boolean(),
});

export const EnsembleScoreListSchema = z.array(EnsembleScoreSchema);
