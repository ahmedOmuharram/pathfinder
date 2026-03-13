import { z } from "zod";
import { requestJsonValidated } from "./http";

const ToolItemSchema = z
  .object({
    name: z.string(),
    description: z.string(),
  })
  .passthrough();

const ToolListResponseSchema = z
  .object({
    tools: z.array(ToolItemSchema),
  })
  .passthrough();

export type ToolItem = z.infer<typeof ToolItemSchema>;

export async function listTools(): Promise<ToolItem[]> {
  const res = await requestJsonValidated(ToolListResponseSchema, "/api/v1/tools");
  return res.tools;
}
