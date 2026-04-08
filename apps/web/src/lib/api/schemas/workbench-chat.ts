/**
 * Zod schemas for workbench chat API responses.
 *
 */
import { z } from "zod";

export const WorkbenchChatResponseSchema = z.object({
  operationId: z.string(),
  streamId: z.string(),
});

export const WorkbenchChatMessageSchema = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string(),
  messageId: z.string().optional(),
  timestamp: z.string().optional(),
  toolCalls: z.array(z.unknown()).optional(),
  citations: z.array(z.unknown()).optional(),
});

export const WorkbenchChatMessageListSchema = z.array(WorkbenchChatMessageSchema);
