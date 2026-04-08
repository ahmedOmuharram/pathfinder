/**
 * Zod schemas for reverse-search responses.
 *
 */
import { z } from "zod";

export const ReverseSearchResultSchema = z.object({
  geneSetId: z.string(),
  name: z.string(),
  searchName: z.string().nullable(),
  recall: z.number(),
  precision: z.number(),
  f1: z.number(),
  estimatedSize: z.number(),
  overlapCount: z.number(),
});

export const ReverseSearchResultListSchema = z.array(ReverseSearchResultSchema);
