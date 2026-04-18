"use client";

import { DefaultChatTransport, type UIMessage } from "ai";
import { useChatRuntime as useAssistantUIChatRuntime } from "@assistant-ui/react-ai-sdk";

import { getAuthHeaders } from "@/lib/api/http";
import { useSessionStore } from "@/state/useSessionStore";

import { buildChatRequestBody } from "./buildRequestBody";
import { createFeedbackAdapter } from "./feedbackAdapter";

interface UseChatRuntimeArgs {
  chatId: string;
  initialMessages?: UIMessage[];
  getCheckpointId?: (threadId: string, parentMessages: UIMessage[]) => Promise<string | null>;
}

const chatIdsWithRewrittenUrl = new Set<string>();

export function useChatRuntime({
  chatId,
  initialMessages,
  getCheckpointId,
}: UseChatRuntimeArgs) {
  return useAssistantUIChatRuntime({
    id: chatId,
    ...(initialMessages !== undefined && { messages: initialMessages }),
    adapters: { feedback: createFeedbackAdapter() },
    transport: new DefaultChatTransport({
      api: "/api/v1/chat",
      headers: () =>
        getAuthHeaders({
          accept: "text/event-stream",
          contentType: "application/json",
        }),
      prepareSendMessagesRequest: async ({ id, messages, trigger, body }) => {
        if (
          !chatIdsWithRewrittenUrl.has(chatId)
          && typeof window !== "undefined"
          && !window.location.pathname.startsWith(`/conversation/${chatId}`)
        ) {
          chatIdsWithRewrittenUrl.add(chatId);
          window.history.replaceState(null, "", `/conversation/${chatId}`);
        }
        const parentCheckpointId =
          getCheckpointId !== undefined
            ? await getCheckpointId(id, messages)
            : null;
        const siteId = useSessionStore.getState().selectedSite;
        return {
          body: buildChatRequestBody({
            chatId,
            siteId,
            id,
            trigger,
            messages,
            parentCheckpointId,
            baseBody: body as Record<string, unknown> | undefined,
          }),
        };
      },
    }),
  });
}
