import { requestJson } from "@/lib/api/http";
import {
  subscribeToOperation,
  type OperationSubscription,
} from "@/lib/operationSubscribe";
import type { ChatSSEEvent, RawSSEData } from "@/lib/sse_events";
import { parseChatSSEEvent } from "@/lib/sse_events";
import type { ChatMention, ModelSelection } from "@pathfinder/shared";

interface StreamChatContext {
  strategyId?: string;
  /** @-mention references to strategies and experiments. */
  mentions?: ChatMention[];
}

interface StreamChatResult {
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
        ...(context?.strategyId != null ? { strategyId: context.strategyId } : {}),
        ...(context?.mentions != null ? { mentions: context.mentions } : {}),
        // Per-request model overrides
        ...(modelSelection?.provider != null
          ? { provider: modelSelection.provider }
          : {}),
        ...(modelSelection?.model != null ? { model: modelSelection.model } : {}),
        ...(modelSelection?.reasoningEffort != null
          ? { reasoningEffort: modelSelection.reasoningEffort }
          : {}),
        // Per-model tuning overrides
        ...(modelSelection?.contextSize != null
          ? { contextSize: modelSelection.contextSize }
          : {}),
        ...(modelSelection?.responseTokens != null
          ? { responseTokens: modelSelection.responseTokens }
          : {}),
        ...(modelSelection?.reasoningBudget != null
          ? { reasoningBudget: modelSelection.reasoningBudget }
          : {}),
        // Disabled tools
        ...(disabledTools != null && disabledTools.length > 0 ? { disabledTools } : {}),
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
    subscription,
  };
}
