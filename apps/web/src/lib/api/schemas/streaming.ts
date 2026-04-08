/**
 * Zod schemas for streaming operation responses.
 *
 */
import { z } from "zod";

export const OperationIdResponseSchema = z
  .object({ operationId: z.string() });

export const ChatOperationResponseSchema = z
  .object({ operationId: z.string(), strategyId: z.string(), entryId: z.string() });
