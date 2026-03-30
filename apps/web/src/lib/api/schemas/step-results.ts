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
  help: z.string().nullable(),
  type: z.string().nullable(),
  isDisplayable: z.boolean(),
  isSortable: z.boolean(),
  isSuggested: z.boolean(),
});

export const AttributesResponseSchema = z.object({
  attributes: z.array(RecordAttributeSchema),
  recordType: z.string(),
});

// ---------------------------------------------------------------------------
// Records
// ---------------------------------------------------------------------------

const ClassificationSchema = z.enum(["TP", "FP", "FN", "TN"]);

const WdkRecordSchema = z.object({
  id: z.array(z.object({ name: z.string(), value: z.string() })),
  attributes: z.record(z.string(), z.string().nullable()),
  _classification: ClassificationSchema.nullable().optional(),
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
  displayName: z.string(),
  id: z.array(z.object({ name: z.string(), value: z.string() })),
  recordClassName: z.string(),
  attributes: z.record(z.string(), z.string().nullable()),
  attributeNames: z.record(z.string(), z.string()),
  tables: z.record(z.string(), z.array(z.unknown())),
  tableErrors: z.array(z.string()),
});

// ---------------------------------------------------------------------------
// Distribution
// ---------------------------------------------------------------------------

const DistributionHistogramBinSchema = z.object({
  value: z.number(),
  binStart: z.string(),
  binEnd: z.string(),
  binLabel: z.string(),
});

const DistributionStatisticsSchema = z.object({
  subsetSize: z.number(),
  subsetMin: z.number().nullable(),
  subsetMax: z.number().nullable(),
  subsetMean: z.number().nullable(),
  numVarValues: z.number(),
  numDistinctValues: z.number(),
  numDistinctEntityRecords: z.number(),
  numMissingCases: z.number(),
});

export const DistributionResponseSchema = z.object({
  histogram: z.array(DistributionHistogramBinSchema),
  statistics: DistributionStatisticsSchema,
});
