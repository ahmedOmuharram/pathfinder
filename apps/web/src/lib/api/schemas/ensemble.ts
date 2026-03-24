/**
 * Zod schemas for ensemble scoring responses.
 *
 * All object schemas use .passthrough() so extra fields from the backend
 * are preserved rather than stripped.
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
