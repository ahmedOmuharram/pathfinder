/**
 * Zod schemas for reverse-search responses.
 *
 * All object schemas use .passthrough() so extra fields from the backend
 * are preserved rather than stripped.
 */
import { z } from "zod";

export const ReverseSearchResultSchema = z.object({
  geneSetId: z.string(),
  name: z.string(),
  searchName: z.string().nullable(),
  recall: z.number(),
  precision: z.number(),
  f1: z.number(),
  resultCount: z.number(),
  overlapCount: z.number(),
});

export const ReverseSearchResultListSchema = z.array(ReverseSearchResultSchema);
