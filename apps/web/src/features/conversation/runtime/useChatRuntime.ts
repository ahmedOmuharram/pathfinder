"use client";

import { useChat } from "@ai-sdk/react";
import {
  type UIMessage,
  lastAssistantMessageIsCompleteWithApprovalResponses,
} from "ai";
import { useAISDKRuntime } from "@assistant-ui/react-ai-sdk";
import { useQueryClient } from "@tanstack/react-query";

import type { Strategy } from "@pathfinder/shared";
import { decisionPresentedSchema } from "@pathfinder/shared/generated/zod/decisionPresentedSchema";
import { geneSetSchema } from "@pathfinder/shared/generated/zod/geneSetSchema";
import { graphClearedSchema } from "@pathfinder/shared/generated/zod/graphClearedSchema";
import { graphSnapshotSchema } from "@pathfinder/shared/generated/zod/graphSnapshotSchema";
import { planArtifactSchema } from "@pathfinder/shared/generated/zod/planArtifactSchema";
import { problemFrameSchema } from "@pathfinder/shared/generated/zod/problemFrameSchema";
import { strategyMetaSchema } from "@pathfinder/shared/generated/zod/strategyMetaSchema";
import { turnUsageSchema } from "@pathfinder/shared/generated/zod/turnUsageSchema";

import { getAuthHeaders } from "@/lib/api/http";
import { beginStrategy } from "@pathfinder/shared/generated/hooks/useBeginStrategy";
import { listStrategiesQueryOptions } from "@pathfinder/shared/generated/hooks/useListStrategies";
import { strategyQueryKey, strategyQueryOptions } from "@/lib/api/strategy";
import { getMyQuotaQueryKey } from "@pathfinder/shared/generated/hooks/useGetMyQuota";
import { listScratchpadNotesQueryOptions } from "@pathfinder/shared/generated/hooks/useListScratchpadNotes";
import { usePlanStore } from "@/state/usePlanStore";
import { useRightRailStore } from "@/state/useRightRailStore";
import { useSessionStore } from "@/state/useSessionStore";
import { useSettingsStore } from "@/state/useSettingsStore";
import { useStrategyStore } from "@/state/strategy/store";

import { buildChatRequestBody } from "./buildRequestBody";
import type { ChatHelpers } from "./chatHelpersContext";
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
}: UseChatRuntimeArgs): {
  runtime: ReturnType<typeof useAISDKRuntime<UIMessage>>;
  chat: ChatHelpers;
} {
  const queryClient = useQueryClient();
  const invalidateConversationList = () => {
    const siteId = useSessionStore.getState().selectedSite;
    void queryClient.invalidateQueries({
      queryKey: listStrategiesQueryOptions({ siteId }).queryKey,
    });
  };
  const transport = new DurableChatTransport({
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
      const { phaseModels, phaseReasoning } = useSettingsStore.getState();
      await beginStrategy(conversationId, { siteId });
      return {
        body: buildChatRequestBody({
          conversationId,
          siteId,
          id,
          trigger,
          messages,
          baseBody: body as Record<string, unknown> | undefined,
          phaseModels,
          phaseReasoning,
        }),
      };
    },
  });

  const chat = useChat<UIMessage>({
    id: conversationId,
    resume: !allowMissing,
    generateId: () => crypto.randomUUID(),
    ...(initialMessages !== undefined && { messages: initialMessages }),
    transport,
    sendAutomaticallyWhen: lastAssistantMessageIsCompleteWithApprovalResponses,
    onData: (dataPart) => {
      switch (dataPart.type) {
        case "data-conversation-title":
          invalidateConversationList();
          break;
        case "data-scratchpad-updated":
          void queryClient.invalidateQueries({
            queryKey: listScratchpadNotesQueryOptions(conversationId).queryKey,
          });
          break;
        case "data-plan-artifact":
          usePlanStore
            .getState()
            .appendPlanArtifact(planArtifactSchema.parse(dataPart.data));
          break;
        case "data-problem-frame":
          useSessionStore
            .getState()
            .setProblemFrame(problemFrameSchema.parse(dataPart.data));
          break;
        case "data-gene-set":
          useSessionStore.getState().recordGeneSet(geneSetSchema.parse(dataPart.data));
          break;
        case "data-graph-snapshot": {
          const snapshot = graphSnapshotSchema.parse(dataPart.data);
          void queryClient.invalidateQueries({
            queryKey: strategyQueryOptions(conversationId).queryKey,
          });
          // Surface the freshly built strategy: switch the rail to the
          // Strategy panel so the user sees the result of the auto-build.
          if (snapshot.nodes.length > 0) {
            useRightRailStore
              .getState()
              .openPanelId("strategy", { strategyStepCount: snapshot.nodes.length });
          }
          break;
        }
        case "data-strategy-meta":
          strategyMetaSchema.parse(dataPart.data);
          break;
        case "data-graph-cleared":
          graphClearedSchema.parse(dataPart.data);
          useStrategyStore.getState().clear();
          void queryClient.invalidateQueries({
            queryKey: strategyQueryOptions(conversationId).queryKey,
          });
          break;
        case "data-decision-presented":
          decisionPresentedSchema.parse(dataPart.data);
          break;
        case "data-turn-usage": {
          const usage = turnUsageSchema.parse(dataPart.data);
          const detailKey = strategyQueryOptions(conversationId).queryKey;
          queryClient.setQueryData<Strategy | null>(detailKey, (prev) =>
            prev == null
              ? prev
              : {
                  ...prev,
                  totalTokens: usage.totalTokens,
                  totalCostUsd: usage.costUsd,
                },
          );
          void queryClient.invalidateQueries({ queryKey: getMyQuotaQueryKey() });
          break;
        }
      }
    },
    onFinish: () => {
      void queryClient.invalidateQueries({
        queryKey: strategyQueryKey(conversationId),
      });
      invalidateConversationList();
      void queryClient.invalidateQueries({ queryKey: getMyQuotaQueryKey() });
    },
  });

  const runtime = useAISDKRuntime(chat, {
    adapters: { feedback: createFeedbackAdapter() },
  });

  return { runtime, chat };
}
