import type {
  ConversationResponse,
  PlanArtifact,
  Strategy,
  StrategyPlan,
} from "@pathfinder/shared";
import { queryOptions } from "@tanstack/react-query";
import type { UIMessage } from "ai";
import { z } from "zod";

import {
  OpenStrategyResponseSchema,
  StepCountsResponseSchema,
  StrategyListItemListSchema,
  StrategySchema,
} from "./schemas/strategy";
import { APIError, requestJson, requestVoid } from "./http";

function withDefaults(
  s: Partial<Strategy> & {
    id: string;
    name: string;
    siteId: string;
    createdAt: string;
    updatedAt: string;
  },
): Strategy {
  return { steps: [], rootStepId: null, recordType: null, isSaved: false, ...s };
}

const ConversationSummarySchema = z.object({
  id: z.uuid(),
  name: z.string(),
  siteId: z.string(),
  experimentId: z.string().nullable(),
  wdkStrategyId: z.number().int().nullable(),
  isSaved: z.boolean(),
  stepCount: z.number().int(),
  estimatedSize: z.number().int().nullable(),
  dismissedAt: z.string().nullable(),
  createdAt: z.string(),
  updatedAt: z.string(),
  recordType: z.string().nullable(),
});

export type ConversationSummary = z.infer<typeof ConversationSummarySchema>;

const ConversationSummaryListSchema = z.array(ConversationSummarySchema);

const ConversationDuplicateResponseSchema = z.object({
  id: z.uuid(),
  name: z.string(),
});

export type ConversationDuplicateResponse = z.infer<
  typeof ConversationDuplicateResponseSchema
>;

export async function listConversations(
  siteId?: string | null,
): Promise<ConversationSummary[]> {
  const raw = await requestJson(
    StrategyListItemListSchema,
    "/api/v1/conversations",
    siteId != null && siteId !== "" ? { query: { siteId } } : {},
  );
  return raw as unknown as ConversationSummary[];
}

export async function listDismissedConversations(
  siteId?: string | null,
): Promise<ConversationSummary[]> {
  const raw = await requestJson(
    StrategyListItemListSchema,
    "/api/v1/conversations/dismissed",
    siteId != null && siteId !== "" ? { query: { siteId } } : {},
  );
  return raw as unknown as ConversationSummary[];
}

export async function getConversation(
  conversationId: string,
): Promise<Strategy | null> {
  try {
    const raw = await requestJson(
      StrategySchema,
      `/api/v1/conversations/${conversationId}`,
    );
    return withDefaults(raw as Parameters<typeof withDefaults>[0]);
  } catch (err) {
    if (err instanceof APIError && err.status === 404) return null;
    throw err;
  }
}

export function conversationDetailOptions(conversationId: string) {
  return queryOptions({
    queryKey: ["conversations", conversationId, "detail"] as const,
    queryFn: () => getConversation(conversationId),
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

export function conversationListOptions(siteId: string) {
  return queryOptions({
    queryKey: ["conversations", "list", siteId] as const,
    queryFn: () => listConversations(siteId),
  });
}

export function dismissedConversationsOptions(siteId: string) {
  return queryOptions({
    queryKey: ["conversations", "dismissed", siteId] as const,
    queryFn: () => listDismissedConversations(siteId),
  });
}

const UIMessagePartSchema = z.looseObject({
  type: z.string(),
});

const PersistedUIMessageSchema = z.object({
  id: z.string(),
  role: z.enum(["system", "user", "assistant"]),
  parts: z.array(UIMessagePartSchema),
  metadata: z.unknown().optional(),
});

const PersistedMessageListSchema = z.array(PersistedUIMessageSchema);

export async function listConversationMessages(
  conversationId: string,
): Promise<UIMessage[]> {
  const rows = await requestJson(
    PersistedMessageListSchema,
    `/api/v1/conversations/${conversationId}/messages`,
  );
  return rows as unknown as UIMessage[];
}

export function conversationMessagesOptions(conversationId: string) {
  return queryOptions({
    queryKey: ["conversations", conversationId, "messages"] as const,
    queryFn: () => listConversationMessages(conversationId),
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

export async function renameConversation(
  conversationId: string,
  name: string,
): Promise<ConversationSummary> {
  const raw = await requestJson(
    ConversationSummarySchema,
    `/api/v1/conversations/${conversationId}`,
    { method: "PATCH", body: { name } },
  );
  return raw;
}

export async function setConversationSaved(
  conversationId: string,
  isSaved: boolean,
): Promise<ConversationSummary> {
  const raw = await requestJson(
    ConversationSummarySchema,
    `/api/v1/conversations/${conversationId}`,
    { method: "PATCH", body: { isSaved } },
  );
  return raw;
}

export async function dismissConversation(
  conversationId: string,
): Promise<void> {
  await requestVoid(`/api/v1/conversations/${conversationId}/dismiss`, {
    method: "POST",
  });
}

export async function restoreConversation(
  conversationId: string,
): Promise<void> {
  await requestVoid(`/api/v1/conversations/${conversationId}/restore`, {
    method: "POST",
  });
}

export async function deleteConversation(
  conversationId: string,
  deleteFromWdk?: boolean,
): Promise<void> {
  await requestVoid(
    `/api/v1/conversations/${conversationId}`,
    deleteFromWdk === true
      ? { method: "DELETE", query: { deleteFromWdk: "true" } }
      : { method: "DELETE" },
  );
}

export async function duplicateConversation(
  conversationId: string,
): Promise<ConversationDuplicateResponse> {
  return await requestJson(
    ConversationDuplicateResponseSchema,
    `/api/v1/conversations/${conversationId}/duplicate`,
    { method: "POST" },
  );
}

export async function syncWdkConversations(
  siteId: string,
): Promise<Strategy[]> {
  const raw = await requestJson(
    StrategyListItemListSchema,
    "/api/v1/conversations/sync-wdk",
    { method: "POST", query: { siteId } },
  );
  return raw.map((s) => withDefaults(s as Parameters<typeof withDefaults>[0]));
}

export async function openConversation(payload: {
  siteId?: string;
  conversationId?: string;
  wdkStrategyId?: number;
}): Promise<{ conversationId: string }> {
  const raw = await requestJson(
    OpenStrategyResponseSchema,
    "/api/v1/conversations/open",
    { method: "POST", body: payload },
  );
  return raw as unknown as { conversationId: string };
}

export async function createConversation(args: {
  name: string;
  siteId: string;
  plan: StrategyPlan;
}): Promise<Strategy> {
  const raw = await requestJson(StrategySchema, "/api/v1/conversations", {
    method: "POST",
    body: args,
  });
  return withDefaults(raw as Parameters<typeof withDefaults>[0]);
}

export async function updateConversation(
  conversationId: string,
  args: {
    name?: string;
    plan?: StrategyPlan | PlanArtifact;
    wdkStrategyId?: number | null;
    isSaved?: boolean;
  },
): Promise<Strategy> {
  const raw = await requestJson(
    StrategySchema,
    `/api/v1/conversations/${conversationId}`,
    { method: "PATCH", body: args },
  );
  return withDefaults(raw as Parameters<typeof withDefaults>[0]);
}

export async function pushConversation(
  conversationId: string,
  args: {
    name: string;
    siteId: string;
    plan: StrategyPlan;
    description?: string | null;
  },
): Promise<Strategy> {
  const raw = await requestJson(
    StrategySchema,
    `/api/v1/conversations/${conversationId}/push`,
    { method: "POST", body: args },
  );
  return withDefaults(raw as Parameters<typeof withDefaults>[0]);
}

export async function computeStepCounts(
  siteId: string,
  plan: StrategyPlan,
): Promise<{ counts: Record<string, number | null> }> {
  return await requestJson(
    StepCountsResponseSchema,
    "/api/v1/conversations/step-counts",
    { method: "POST", body: { siteId, plan } },
  );
}

export interface UndoTurnResponse {
  messageCount: number;
  strategy: Record<string, unknown> | null;
  wdkStrategyId: number | null;
}

const UndoTurnResponseSchema = z.object({
  messageCount: z.number(),
  strategy: z.record(z.string(), z.unknown()).nullable(),
  wdkStrategyId: z.number().nullable(),
});

export async function undoTurn(
  streamId: string,
  entryId: string,
  traceId?: string | null,
): Promise<UndoTurnResponse> {
  return await requestJson(
    UndoTurnResponseSchema,
    `/api/v1/chat/${streamId}/undo`,
    {
      method: "POST",
      body: {
        entryId,
        ...(traceId != null && traceId !== "" ? { traceId } : {}),
      },
    },
  );
}

export type { ConversationResponse };
