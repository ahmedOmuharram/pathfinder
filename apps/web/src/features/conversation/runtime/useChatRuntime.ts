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

const chatIdsWithRewrittenUrl = new Set<string>();

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
          // The StrategyPanel reads the full Strategy shape from the
          // conversation-detail query; the snapshot payload is a compact
          // nodes/edges summary, not a full Strategy. Invalidate so the
          // panel refetches the authoritative AST from the server as the
          // turn builds the strategy — otherwise users only see the
          // strategy after manually refreshing.
          void queryClient.invalidateQueries({
            queryKey: conversationDetailOptions(conversationId).queryKey,
          });
          break;
        case "data-strategy-update":
          useStrategyStore
            .getState()
            .applyPatch(strategyPatchSchema.parse(dataPart.data));
          void queryClient.invalidateQueries({
            queryKey: conversationDetailOptions(conversationId).queryKey,
          });
          break;
        case "data-strategy-meta":
          useStrategyStore
            .getState()
            .setLatestStrategyMeta(strategyMetaSchema.parse(dataPart.data));
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
  };
  return useAssistantUIChatRuntime(runtimeOptions);
}
