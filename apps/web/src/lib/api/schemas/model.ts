/**
 * Zod schemas for Model catalog API responses.
 *
 * All object schemas use .passthrough() so extra fields from the backend
 * are preserved rather than stripped.
 */
import { z } from "zod";

// ---------------------------------------------------------------------------
// Model Catalog
// ---------------------------------------------------------------------------

const ModelProviderSchema = z.enum(["openai", "anthropic", "google", "ollama", "mock"]);

const ReasoningEffortSchema = z.enum(["none", "low", "medium", "high"]);

export const ModelCatalogEntrySchema = z.object({
  id: z.string(),
  name: z.string(),
  provider: ModelProviderSchema,
  model: z.string(),
  supportsReasoning: z.boolean(),
  enabled: z.boolean(),
  contextSize: z.number(),
  defaultReasoningBudget: z.number(),
  description: z.string(),
  inputPrice: z.number(),
  cachedInputPrice: z.number(),
  outputPrice: z.number(),
});

export const ModelCatalogResponseSchema = z.object({
  models: z.array(ModelCatalogEntrySchema),
  default: z.string(),
  defaultReasoningEffort: ReasoningEffortSchema,
});
