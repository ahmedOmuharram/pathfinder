/**
 * Zod schemas for ControlSet API responses.
 */
import { z } from "zod";
import { DateTimeString } from "./common";

export const ControlSetSchema = z.object({
  id: z.string(),
  name: z.string(),
  siteId: z.string(),
  recordType: z.string(),
  positiveIds: z.array(z.string()),
  negativeIds: z.array(z.string()),
  source: z.string().nullable().optional(),
  tags: z.array(z.string()).default([]),
  provenanceNotes: z.string().nullable().optional(),
  version: z.number().default(1),
  isPublic: z.boolean().default(false),
  createdAt: DateTimeString,
  userId: z.string().nullable().optional(),
});

export const ControlSetListSchema = z.array(ControlSetSchema);
