import { requestJson } from "@/lib/api/http";
import { ChatOperationResponseSchema } from "@/lib/api/schemas/streaming";
import {
  subscribeToOperation,
  type OperationSubscription,
} from "@/lib/operationSubscribe";
import type { ChatSSEEvent, RawSSEData } from "@/lib/sse_events";
import { parseChatSSEEvent } from "@/lib/sse_events";
import type { ChatMention, PipelineConfig } from "@pathfinder/shared";

interface StreamChatContext {
  strategyId?: string;
  /** @-mention references to strategies and experiments. */
  mentions?: ChatMention[];
  /** Structured metadata from UI interactions (e.g. plan approval). */
  metadata?: Record<string, unknown>;
}

interface StreamChatResult {
  operationId: string;
  strategyId: string;
  entryId: string;
  subscription: OperationSubscription;
}

export async function streamChat(
  message: string,
  siteId: string,
  options: {
    onMessage: (event: ChatSSEEvent) => void;
    onError?: (error: Error) => void;
    onComplete?: () => void;
  },
  context?: StreamChatContext,
  signal?: AbortSignal,
  pipeline?: PipelineConfig,
): Promise<StreamChatResult> {
  // POST to start the chat operation.
  const resp = await requestJson(ChatOperationResponseSchema, "/api/v1/chat",
    {
      method: "POST",
      body: {
        message,
        siteId,
        ...(context?.strategyId != null ? { strategyId: context.strategyId } : {}),
        ...(context?.mentions != null ? { mentions: context.mentions } : {}),
        ...(context?.metadata != null && Object.keys(context.metadata).length > 0
          ? { metadata: context.metadata }
          : {}),
        // Pipeline config (per-phase model + reasoning effort)
        ...(pipeline != null ? { pipeline } : {}),
      },
      ...(signal != null ? { signal } : {}),
    },
  );

  // Subscribe for events.  Raw SSE payloads are JSON objects with varying shapes
  // depending on the event type; parseChatSSEEvent handles narrowing.
  const subscription = subscribeToOperation<RawSSEData>(resp.operationId, {
    onEvent: ({ type, data }) => {
      const event = parseChatSSEEvent({ type, data });
      if (event) options.onMessage(event);
    },
    ...(options.onComplete != null ? { onComplete: options.onComplete } : {}),
    ...(options.onError != null ? { onError: options.onError } : {}),
    endEventTypes: new Set(["message_end"]),
  });

  return {
    operationId: resp.operationId,
    strategyId: resp.strategyId,
    entryId: resp.entryId,
    subscription,
  };
}
