import { requestJson } from "@/lib/api/http";
import {
  subscribeToOperation,
  type OperationSubscription,
} from "@/lib/operationSubscribe";
import type { ChatSSEEvent, RawSSEData } from "@/lib/sse_events";
import { parseChatSSEEvent } from "@/lib/sse_events";
import type { ChatMention, ModelSelection } from "@pathfinder/shared";

export interface StreamChatContext {
  strategyId?: string;
  /** @-mention references to strategies and experiments. */
  mentions?: ChatMention[];
}

export interface StreamChatResult {
  operationId: string;
  strategyId: string;
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
  modelSelection?: ModelSelection,
  disabledTools?: string[],
): Promise<StreamChatResult> {
  // POST to start the chat operation.
  const resp = await requestJson<{ operationId: string; strategyId: string }>(
    "/api/v1/chat",
    {
      method: "POST",
      body: {
        message,
        siteId,
        strategyId: context?.strategyId,
        mentions: context?.mentions,
        // Per-request model overrides
        provider: modelSelection?.provider,
        model: modelSelection?.model,
        reasoningEffort: modelSelection?.reasoningEffort,
        // Per-model tuning overrides
        contextSize: modelSelection?.contextSize,
        responseTokens: modelSelection?.responseTokens,
        reasoningBudget: modelSelection?.reasoningBudget,
        // Disabled tools
        disabledTools: disabledTools?.length ? disabledTools : undefined,
      },
      signal,
    },
  );

  // Subscribe for events.  Raw SSE payloads are JSON objects with varying shapes
  // depending on the event type; parseChatSSEEvent handles narrowing.
  const subscription = subscribeToOperation<RawSSEData>(resp.operationId, {
    onEvent: ({ type, data }) => {
      const event = parseChatSSEEvent({ type, data });
      if (event) options.onMessage(event);
    },
    onComplete: options.onComplete,
    onError: options.onError,
    endEventTypes: new Set(["message_end"]),
  });

  return {
    operationId: resp.operationId,
    strategyId: resp.strategyId,
    subscription,
  };
}
