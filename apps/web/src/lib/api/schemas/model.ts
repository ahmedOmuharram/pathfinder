/**
 * Zod schemas for Model catalog API responses.
 *
 */
import { z } from "zod";

// ---------------------------------------------------------------------------
// Model Catalog
// ---------------------------------------------------------------------------

const ModelProviderSchema = z.enum(["openai", "anthropic", "google", "ollama", "mock"]);

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
  defaultProvider: ModelProviderSchema,
  defaultTier: z.enum(["quality", "balanced", "fast"]),
});
