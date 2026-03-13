import { z } from "zod";

export const SystemConfigResponseSchema = z
  .object({
    chat_provider: z.string(),
    llm_configured: z.boolean(),
    providers: z.object({
      openai: z.boolean(),
      anthropic: z.boolean(),
      google: z.boolean(),
    }),
  })
  .passthrough();

export type SystemConfigResponse = z.infer<typeof SystemConfigResponseSchema>;
