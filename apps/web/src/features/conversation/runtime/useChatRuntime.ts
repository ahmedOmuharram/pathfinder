"use client";

import { type UIMessage } from "ai";
import {
  useChatRuntime as useAssistantUIChatRuntime,
  type UseChatRuntimeOptions,
} from "@assistant-ui/react-ai-sdk";
import { useQueryClient } from "@tanstack/react-query";

import type { Strategy } from "@pathfinder/shared";
import { decisionPresentedSchema } from "@pathfinder/shared/generated/zod/decisionPresentedSchema";
import { geneSetSchema } from "@pathfinder/shared/generated/zod/geneSetSchema";
import { graphClearedSchema } from "@pathfinder/shared/generated/zod/graphClearedSchema";
import { graphSnapshotSchema } from "@pathfinder/shared/generated/zod/graphSnapshotSchema";
import { planArtifactSchema } from "@pathfinder/shared/generated/zod/planArtifactSchema";
import { problemFrameSchema } from "@pathfinder/shared/generated/zod/problemFrameSchema";
import { strategyMetaSchema } from "@pathfinder/shared/generated/zod/strategyMetaSchema";
import { strategyPatchSchema } from "@pathfinder/shared/generated/zod/strategyPatchSchema";
import { turnUsageSchema } from "@pathfinder/shared/generated/zod/turnUsageSchema";

import { getAuthHeaders } from "@/lib/api/http";
import {
  conversationDetailOptions,
  conversationListOptions,
} from "@/lib/api/conversations";
import { userQuotaQueryKey } from "@/lib/api/quota";
import { scratchpadNotesOptions } from "@/lib/api/scratchpad";
import { usePlanStore } from "@/state/usePlanStore";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/strategy/store";

import { buildChatRequestBody } from "./buildRequestBody";
import { DurableChatTransport } from "./DurableChatTransport";
import { createFeedbackAdapter } from "./feedbackAdapter";

interface UseChatRuntimeArgs {
  conversationId: string;
  initialMessages?: UIMessage[];
  allowMissing?: boolean;
}

export function useChatRuntime({
  conversationId,
  initialMessages,
  allowMissing = false,
}: UseChatRuntimeArgs) {
  const queryClient = useQueryClient();
  const invalidateConversationList = () => {
    const siteId = useSessionStore.getState().selectedSite;
    void queryClient.invalidateQueries({
      queryKey: conversationListOptions(siteId).queryKey,
    });
  };
  // `resume` isn't on the public UseChatRuntimeOptions type but is spread
  // through to the underlying useChat at runtime.
  const runtimeOptions: UseChatRuntimeOptions<UIMessage> & {
    resume?: boolean;
  } = {
    id: conversationId,
    resume: !allowMissing,
    generateId: () => crypto.randomUUID(),
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
          // Validate shape; the StrategyPanel reads the full Strategy from the
          // conversation-detail query. Invalidate so the panel refetches the
          // authoritative AST from the server as the turn builds the strategy.
          graphSnapshotSchema.parse(dataPart.data);
          void queryClient.invalidateQueries({
            queryKey: conversationDetailOptions(conversationId).queryKey,
          });
          break;
        case "data-strategy-update":
          strategyPatchSchema.parse(dataPart.data);
          void queryClient.invalidateQueries({
            queryKey: conversationDetailOptions(conversationId).queryKey,
          });
          break;
        case "data-strategy-meta":
          strategyMetaSchema.parse(dataPart.data);
          break;
        case "data-graph-cleared":
          graphClearedSchema.parse(dataPart.data);
          useStrategyStore.getState().clear();
          void queryClient.invalidateQueries({
            queryKey: conversationDetailOptions(conversationId).queryKey,
          });
          break;
        case "data-decision-presented":
          decisionPresentedSchema.parse(dataPart.data);
          break;
        case "data-turn-usage": {
          const usage = turnUsageSchema.parse(dataPart.data);
          const detailKey =
            conversationDetailOptions(conversationId).queryKey;
          queryClient.setQueryData<Strategy | null>(detailKey, (prev) =>
            prev == null
              ? prev
              : {
                  ...prev,
                  totalTokens: usage.totalTokens,
                  totalCostUsd: usage.costUsd,
                },
          );
          void queryClient.invalidateQueries({ queryKey: userQuotaQueryKey });
          break;
        }
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
    transport: new DurableChatTransport({
      conversationId,
      eventsUrlFor: (id) => `/api/v1/conversations/${id}/events`,
      api: "/api/v1/chat",
      headers: () =>
        getAuthHeaders({
          accept: "text/event-stream",
          contentType: "application/json",
        }),
      prepareSendMessagesRequest: async ({ id, messages, trigger, body }) => {
        const siteId = useSessionStore.getState().selectedSite;
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
  };
  return useAssistantUIChatRuntime(runtimeOptions);
}
