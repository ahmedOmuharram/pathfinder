/**
 * Zod schemas for step result browsing responses (attributes, records,
 * distributions).
 */
import { z } from "zod";

// ---------------------------------------------------------------------------
// Record attributes
// ---------------------------------------------------------------------------

export const RecordAttributeSchema = z.object({
  name: z.string(),
  displayName: z.string(),
  help: z.string().nullable().optional(),
  type: z.string().nullable().optional(),
  isDisplayable: z.boolean().optional(),
  isSortable: z.boolean().optional(),
  isSuggested: z.boolean().optional(),
});

export const AttributesResponseSchema = z.object({
  attributes: z.array(RecordAttributeSchema),
  recordType: z.string(),
});

// ---------------------------------------------------------------------------
// Records
// ---------------------------------------------------------------------------

const WdkRecordSchema = z.object({
  id: z.array(z.object({ name: z.string(), value: z.string() })),
  attributes: z.record(z.string(), z.string().nullable()),
  _classification: z.unknown().nullable().optional(),
});

export const RecordsResponseSchema = z.object({
  records: z.array(WdkRecordSchema),
  meta: z.object({
    totalCount: z.number(),
    displayTotalCount: z.number(),
    responseCount: z.number(),
    pagination: z.object({ offset: z.number(), numRecords: z.number() }),
    attributes: z.array(z.string()),
    tables: z.array(z.string()),
  }),
});

// ---------------------------------------------------------------------------
// Record detail
// ---------------------------------------------------------------------------

export const RecordDetailSchema = z.object({
  id: z.array(z.object({ name: z.string(), value: z.string() })).optional(),
  attributes: z.record(z.string(), z.string().nullable()).optional(),
  attributeNames: z.record(z.string(), z.string()).optional(),
  tables: z.record(z.string(), z.array(z.unknown())).optional(),
  recordType: z.string().optional(),
});

// ---------------------------------------------------------------------------
// Distribution
// ---------------------------------------------------------------------------

const DistributionHistogramBinSchema = z.object({
  binLabel: z.string().optional(),
  binStart: z.string().optional(),
  value: z.number(),
});

export const DistributionResponseSchema = z.object({
  histogram: z.array(DistributionHistogramBinSchema).optional(),
  distribution: z.record(z.string(), z.number()).optional(),
  total: z.number().optional(),
  attributeName: z.string().optional(),
});
