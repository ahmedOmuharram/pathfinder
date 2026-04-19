import { z } from "zod";

export const RefineResponseSchema = z.object({
  success: z.boolean(),
  newStepId: z.number().optional(),
});
