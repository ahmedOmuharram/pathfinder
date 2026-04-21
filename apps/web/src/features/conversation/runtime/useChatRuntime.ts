"use client";

import { DefaultChatTransport, type UIMessage } from "ai";
import { useChatRuntime as useAssistantUIChatRuntime } from "@assistant-ui/react-ai-sdk";
import { useQueryClient } from "@tanstack/react-query";

import { decisionPresentedSchema } from "@pathfinder/shared/generated/zod/decisionPresentedSchema";
import { geneSetSchema } from "@pathfinder/shared/generated/zod/geneSetSchema";
import { graphClearedSchema } from "@pathfinder/shared/generated/zod/graphClearedSchema";
import { graphSnapshotSchema } from "@pathfinder/shared/generated/zod/graphSnapshotSchema";
import { planArtifactSchema } from "@pathfinder/shared/generated/zod/planArtifactSchema";
import { problemFrameSchema } from "@pathfinder/shared/generated/zod/problemFrameSchema";
import { strategyMetaSchema } from "@pathfinder/shared/generated/zod/strategyMetaSchema";
import { strategyPatchSchema } from "@pathfinder/shared/generated/zod/strategyPatchSchema";

import { getAuthHeaders } from "@/lib/api/http";
import { conversationListOptions } from "@/lib/api/conversations";
import { userQuotaQueryKey } from "@/lib/api/quota";
import { scratchpadNotesOptions } from "@/lib/api/scratchpad";
import { usePlanStore } from "@/state/usePlanStore";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/strategy/store";

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
  const invalidateConversationList = () => {
    const siteId = useSessionStore.getState().selectedSite;
    void queryClient.invalidateQueries({
      queryKey: conversationListOptions(siteId).queryKey,
    });
  };
  return useAssistantUIChatRuntime({
    id: conversationId,
    ...(initialMessages !== undefined && { messages: initialMessages }),
    adapters: { feedback: createFeedbackAdapter() },
    onData: (dataPart) => {
      switch (dataPart.type) {
        case "data-conversation-title":
          invalidateConversationList();
          break;
        case "data-scratchpad-updated":
          void queryClient.invalidateQueries({
            queryKey: scratchpadNotesOptions(conversationId).queryKey,
          });
          break;
        case "data-plan-artifact":
          usePlanStore
            .getState()
            .setActivePlanArtifact(planArtifactSchema.parse(dataPart.data));
          break;
        case "data-problem-frame":
          useSessionStore
            .getState()
            .setProblemFrame(problemFrameSchema.parse(dataPart.data));
          break;
        case "data-gene-set":
          useSessionStore
            .getState()
            .recordGeneSet(geneSetSchema.parse(dataPart.data));
          break;
        case "data-graph-snapshot":
          useStrategyStore
            .getState()
            .applyGraphSnapshot(graphSnapshotSchema.parse(dataPart.data));
          break;
        case "data-strategy-update":
          useStrategyStore
            .getState()
            .applyPatch(strategyPatchSchema.parse(dataPart.data));
          break;
        case "data-strategy-meta":
          useStrategyStore
            .getState()
            .setLatestStrategyMeta(strategyMetaSchema.parse(dataPart.data));
          break;
        case "data-graph-cleared":
          graphClearedSchema.parse(dataPart.data);
          useStrategyStore.getState().clear();
          break;
        case "data-decision-presented":
          decisionPresentedSchema.parse(dataPart.data);
          break;
      }
    },
    onFinish: () => {
      void queryClient.invalidateQueries({
        queryKey: ["conversations", conversationId, "detail"],
      });
      void queryClient.invalidateQueries({
        queryKey: ["conversations", conversationId, "messages"],
      });
      invalidateConversationList();
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
