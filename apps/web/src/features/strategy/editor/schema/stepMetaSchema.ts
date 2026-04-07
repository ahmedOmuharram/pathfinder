import { z } from "zod";

export const stepMetaSchema = z.object({
  name: z.string().trim().min(1, { message: "Step name is required" }),
  description: z.string(),
});

export type StepMetaValues = z.infer<typeof stepMetaSchema>;
