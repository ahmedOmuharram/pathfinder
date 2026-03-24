/**
 * Zod schemas for Site / Search / ParamSpec API responses.
 *
 * All object schemas use .passthrough() so extra fields from the backend
 * are preserved rather than stripped.
 */
import { z } from "zod";

// ---------------------------------------------------------------------------
// VEuPathDB Site
// ---------------------------------------------------------------------------

export const VEuPathDBSiteSchema = z.object({
  id: z.string(),
  name: z.string(),
  displayName: z.string(),
  baseUrl: z.string(),
  projectId: z.string(),
  isPortal: z.boolean(),
});

export const VEuPathDBSiteListSchema = z.array(VEuPathDBSiteSchema);

// ---------------------------------------------------------------------------
// Record Type
// ---------------------------------------------------------------------------

export const RecordTypeSchema = z.object({
  name: z.string(),
  displayName: z.string(),
  description: z.string().nullable().optional(),
});

export const RecordTypeListSchema = z.array(RecordTypeSchema);

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export const SearchSchema = z.object({
  name: z.string(),
  displayName: z.string(),
  description: z.string().nullable().optional(),
  recordType: z.string(),
});

export const SearchListSchema = z.array(SearchSchema);

// ---------------------------------------------------------------------------
// ParamSpec
// ---------------------------------------------------------------------------

export const ParamSpecSchema = z.object({
  name: z.string(),
  displayName: z.string().nullable().optional(),
  type: z.string(),
  allowEmptyValue: z.boolean(),
  allowMultipleValues: z.boolean().nullable().optional(),
  multiPick: z.boolean().nullable().optional(),
  minSelectedCount: z.number().nullable().optional(),
  maxSelectedCount: z.number().nullable().optional(),
  countOnlyLeaves: z.boolean(),
  initialDisplayValue: z.unknown().nullable().optional(),
  vocabulary: z.unknown().nullable().optional(),
  min: z.number().nullable().optional(),
  max: z.number().nullable().optional(),
  increment: z.number().nullable().optional(),
  isNumber: z.boolean(),
  // WDK UI metadata (new — for widget dispatch)
  displayType: z.string().nullable().optional(),
  isVisible: z.boolean().optional(),
  group: z.string().nullable().optional(),
  dependentParams: z.array(z.string()).optional(),
  help: z.string().nullable().optional(),
});

export const ParamSpecListSchema = z.array(ParamSpecSchema);

// ---------------------------------------------------------------------------
// Search Validation
// ---------------------------------------------------------------------------

const SearchValidationErrorsSchema = z.object({
  general: z.array(z.string()).optional(),
  byKey: z.record(z.string(), z.array(z.string())).optional(),
});

const SearchValidationPayloadSchema = z.object({
  isValid: z.boolean(),
  normalizedContextValues: z.record(z.string(), z.unknown()).optional(),
  errors: SearchValidationErrorsSchema.optional(),
});

export const SearchValidationResponseSchema = z.object({
  validation: SearchValidationPayloadSchema,
});
