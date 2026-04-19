"use client";

import { DefaultChatTransport, type UIMessage } from "ai";
import { useChatRuntime as useAssistantUIChatRuntime } from "@assistant-ui/react-ai-sdk";
import { useQueryClient } from "@tanstack/react-query";

import { getAuthHeaders } from "@/lib/api/http";
import { conversationListOptions } from "@/lib/api/conversations";
import { userQuotaQueryKey } from "@/lib/api/quota";
import { useSessionStore } from "@/state/useSessionStore";

import { buildChatRequestBody } from "./buildRequestBody";
import { createFeedbackAdapter } from "./feedbackAdapter";

interface UseChatRuntimeArgs {
  conversationId: string;
  initialMessages?: UIMessage[];
}

const chatIdsWithRewrittenUrl = new Set<string>();

export function useChatRuntime({
  conversationId,
  initialMessages,
}: UseChatRuntimeArgs) {
  const queryClient = useQueryClient();
  return useAssistantUIChatRuntime({
    id: conversationId,
    ...(initialMessages !== undefined && { messages: initialMessages }),
    adapters: { feedback: createFeedbackAdapter() },
    onFinish: () => {
      const siteId = useSessionStore.getState().selectedSite;
      void queryClient.invalidateQueries({
        queryKey: ["conversations", conversationId, "detail"],
      });
      void queryClient.invalidateQueries({
        queryKey: conversationListOptions(siteId).queryKey,
      });
      void queryClient.invalidateQueries({ queryKey: userQuotaQueryKey });
    },
    transport: new DefaultChatTransport({
      api: "/api/v1/chat",
      headers: () =>
        getAuthHeaders({
          accept: "text/event-stream",
          contentType: "application/json",
        }),
      prepareSendMessagesRequest: async ({ id, messages, trigger, body }) => {
        const siteId = useSessionStore.getState().selectedSite;
        const conversationPath = `/${siteId}/conversation/${conversationId}`;
        if (
          !chatIdsWithRewrittenUrl.has(conversationId)
          && typeof window !== "undefined"
          && !window.location.pathname.startsWith(conversationPath)
        ) {
          chatIdsWithRewrittenUrl.add(conversationId);
          window.history.replaceState(null, "", conversationPath);
        }
        return {
          body: buildChatRequestBody({
            conversationId,
            siteId,
            id,
            trigger,
            messages,
            baseBody: body as Record<string, unknown> | undefined,
          }),
        };
      },
    }),
  });
}
