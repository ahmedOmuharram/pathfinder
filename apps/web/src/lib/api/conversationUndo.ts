import { z } from "zod";

import { requestJson } from "./http";

export interface UndoTurnResponse {
  messageCount: number;
  strategy: Record<string, unknown> | null;
  wdkStrategyId: number | null;
}

const UndoTurnResponseSchema = z.object({
  messageCount: z.number(),
  strategy: z.record(z.string(), z.unknown()).nullable(),
  wdkStrategyId: z.number().nullable(),
});

export async function undoTurn(
  streamId: string,
  entryId: string,
  traceId?: string | null,
): Promise<UndoTurnResponse> {
  return await requestJson(
    UndoTurnResponseSchema,
    `/api/v1/chat/${streamId}/undo`,
    {
      method: "POST",
      body: {
        entryId,
        ...(traceId != null && traceId !== "" ? { traceId } : {}),
      },
    },
  );
}
