import { z } from "zod";

export const SystemConfigResponseSchema = z
  .object({
    chatProvider: z.string(),
    llmConfigured: z.boolean(),
    providers: z.object({
      openai: z.boolean(),
      anthropic: z.boolean(),
      google: z.boolean(),
      ollama: z.boolean(),
    }),
  })
  .passthrough();

export type SystemConfigResponse = z.infer<typeof SystemConfigResponseSchema>;
