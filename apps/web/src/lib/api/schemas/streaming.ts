/**
 * Zod schemas for streaming operation responses.
 *
 * All object schemas use .passthrough() so extra fields from the backend
 * are preserved rather than stripped.
 */
import { z } from "zod";

export const OperationIdResponseSchema = z
  .object({ operationId: z.string() });

export const ChatOperationResponseSchema = z
  .object({ operationId: z.string(), strategyId: z.string() });
