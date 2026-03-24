/**
 * Zod schemas for GeneSet API responses.
 *
 * All object schemas use .passthrough() so extra fields from the backend
 * are preserved rather than stripped.
 */
import { z } from "zod";
import { DateTimeString } from "./common";

const GeneSetSourceSchema = z.enum(["strategy", "paste", "upload", "derived", "saved"]);

export const GeneSetSchema = z.object({
  id: z.string(),
  name: z.string(),
  source: GeneSetSourceSchema,
  geneIds: z.array(z.string()),
  siteId: z.string(),
  createdAt: DateTimeString,
  geneCount: z.number(),
  stepCount: z.number().default(1),
  wdkStrategyId: z.number().nullable().optional(),
  wdkStepId: z.number().nullable().optional(),
  searchName: z.string().nullable().optional(),
  recordType: z.string().nullable().optional(),
  parameters: z.record(z.string(), z.string()).nullable().optional(),
  parentSetIds: z.array(z.string()).optional(),
  operation: z.enum(["intersect", "union", "minus"]).nullable().optional(),
  userId: z.string().nullable().optional(),
});

export const GeneSetListSchema = z.array(GeneSetSchema);
