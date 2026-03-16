import { describe, expect, it } from "vitest";
import { ModelCatalogEntrySchema, ModelCatalogResponseSchema } from "./model";

const validEntry = {
  id: "openai/gpt-5",
  name: "GPT-5",
  provider: "openai" as const,
  model: "gpt-5",
  supportsReasoning: true,
  enabled: true,
  contextSize: 400_000,
  defaultReasoningBudget: 0,
  description: "OpenAI GPT-5",
  inputPrice: 2.5,
  cachedInputPrice: 1.25,
  outputPrice: 10,
};

describe("ModelCatalogEntrySchema", () => {
  it("parses a valid entry", () => {
    const result = ModelCatalogEntrySchema.safeParse(validEntry);
    expect(result.success).toBe(true);
    expect(result.data?.id).toBe("openai/gpt-5");
  });

  it("passes through extra fields", () => {
    const result = ModelCatalogEntrySchema.safeParse({
      ...validEntry,
      maxTokens: 128000,
    });
    expect(result.success).toBe(true);
    expect((result.data as Record<string, unknown>).maxTokens).toBe(128000);
  });

  it("rejects invalid provider enum", () => {
    const result = ModelCatalogEntrySchema.safeParse({
      ...validEntry,
      provider: "mistral",
    });
    expect(result.success).toBe(false);
  });

  it("rejects missing required fields", () => {
    const result = ModelCatalogEntrySchema.safeParse({
      id: "openai/gpt-5",
    });
    expect(result.success).toBe(false);
  });
});

describe("ModelCatalogResponseSchema", () => {
  const validResponse = {
    models: [validEntry],
    default: "openai/gpt-5",
    defaultReasoningEffort: "medium" as const,
  };

  it("parses a valid catalog response", () => {
    const result = ModelCatalogResponseSchema.safeParse(validResponse);
    expect(result.success).toBe(true);
    expect(result.data?.models).toHaveLength(1);
    expect(result.data?.default).toBe("openai/gpt-5");
  });

  it("passes through extra fields", () => {
    const result = ModelCatalogResponseSchema.safeParse({
      ...validResponse,
      version: 2,
    });
    expect(result.success).toBe(true);
    expect((result.data as Record<string, unknown>).version).toBe(2);
  });

  it("rejects invalid reasoningEffort enum", () => {
    const result = ModelCatalogResponseSchema.safeParse({
      ...validResponse,
      defaultReasoningEffort: "ultra",
    });
    expect(result.success).toBe(false);
  });

  it("rejects missing models array", () => {
    const result = ModelCatalogResponseSchema.safeParse({
      default: "openai/gpt-5",
      defaultReasoningEffort: "medium",
    });
    expect(result.success).toBe(false);
  });
});
