/**
 * Zod schemas for gene confidence scoring responses.
 */
import { z } from "zod";

export const GeneConfidenceScoreSchema = z.object({
  geneId: z.string(),
  compositeScore: z.number(),
  classificationScore: z.number(),
  ensembleScore: z.number(),
  enrichmentScore: z.number(),
});

export const GeneConfidenceScoreListSchema = z.array(GeneConfidenceScoreSchema);
