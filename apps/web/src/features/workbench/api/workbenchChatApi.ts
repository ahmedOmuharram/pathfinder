import { requestJson } from "@/lib/api/http";
import {
  WorkbenchChatResponseSchema,
  WorkbenchChatMessageSchema,
  WorkbenchChatMessageListSchema,
} from "@/lib/api/schemas/workbench-chat";
import type { z } from "zod";
import type { ChatSSEEvent } from "@/lib/sse_events";
import type { RawSSEData } from "@/lib/sse_events";
import { parseChatSSEEvent } from "@/lib/sse_events";
import {
  subscribeToOperation,
  type OperationSubscription,
  type SubscribeOptions,
} from "@/lib/operationSubscribe";

type WorkbenchChatResponse = z.infer<typeof WorkbenchChatResponseSchema>;
type WorkbenchChatMessage = z.infer<typeof WorkbenchChatMessageSchema>;

async function postWorkbenchChat(
  experimentId: string,
  message: string,
  siteId: string,
  options?: { model?: string; signal?: AbortSignal },
): Promise<WorkbenchChatResponse> {
  const body: { message: string; siteId: string; model?: string } = { message, siteId };
  if (options?.model != null) body.model = options.model;
  return requestJson(
    WorkbenchChatResponseSchema,
    `/api/v1/experiments/${experimentId}/chat`,
    {
      method: "POST",
      body,
      ...(options?.signal != null ? { signal: options.signal } : {}),
    },
  );
}

export async function getWorkbenchChatMessages(
  experimentId: string,
): Promise<WorkbenchChatMessage[]> {
  return requestJson(
    WorkbenchChatMessageListSchema,
    `/api/v1/experiments/${experimentId}/chat/messages`,
  );
}

export function streamWorkbenchChat(
  experimentId: string,
  message: string,
  siteId: string,
  callbacks: {
    onMessage: (event: ChatSSEEvent) => void;
    onError?: (error: Error) => void;
    onComplete?: () => void;
  },
  options?: { model?: string; signal?: AbortSignal },
): {
  promise: Promise<{ operationId: string; streamId: string }>;
  cancel: () => void;
} {
  let subscription: OperationSubscription | null = null;

  const promise = (async () => {
    const { operationId, streamId } = await postWorkbenchChat(
      experimentId,
      message,
      siteId,
      options,
    );

    const subscribeOpts: SubscribeOptions<RawSSEData> = {
      onEvent: ({ type, data }) => {
        const parsed = parseChatSSEEvent({ type, data });
        if (parsed != null) callbacks.onMessage(parsed);
      },
      endEventTypes: new Set(["message_end"]),
    };
    if (callbacks.onError != null) subscribeOpts.onError = callbacks.onError;
    if (callbacks.onComplete != null) subscribeOpts.onComplete = callbacks.onComplete;
    subscription = subscribeToOperation<RawSSEData>(operationId, subscribeOpts);

    return { operationId, streamId };
  })();

  return {
    promise,
    cancel: () => subscription?.unsubscribe(),
  };
}
