import type {
  ConversationResponse,
  PlanArtifact,
  Strategy,
  StrategyAst,
} from "@pathfinder/shared";
import { conversationResponseSchema } from "@pathfinder/shared/generated/zod/conversationResponseSchema";
import { openConversationResponseSchema } from "@pathfinder/shared/generated/zod/openConversationResponseSchema";
import { stepCountsResponseSchema } from "@pathfinder/shared/generated/zod/stepCountsResponseSchema";
import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { APIError, requestJson, requestVoid } from "./http";

const conversationListSchema = z.array(conversationResponseSchema);

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
  parentConversationId: z.uuid().nullable().optional(),
  parentMessageId: z.uuid().nullable().optional(),
});

export type ConversationSummary = z.infer<typeof ConversationSummarySchema>;


export async function listConversations(
  siteId?: string | null,
): Promise<ConversationSummary[]> {
  const raw = await requestJson(
    conversationListSchema,
    "/api/v1/conversations",
    siteId != null && siteId !== "" ? { query: { siteId } } : {},
  );
  return raw as unknown as ConversationSummary[];
}

export async function listDismissedConversations(
  siteId?: string | null,
): Promise<ConversationSummary[]> {
  const raw = await requestJson(
    conversationListSchema,
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
      conversationResponseSchema,
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

export async function forkConversation(
  sourceConversationId: string,
  fromMessageId: string,
): Promise<ConversationSummary> {
  const raw = await requestJson(
    ConversationSummarySchema,
    `/api/v1/conversations/${sourceConversationId}/fork`,
    { method: "POST", body: { fromMessageId } },
  );
  return raw;
}

export async function revertConversationToMessage(
  conversationId: string,
  messageId: string,
): Promise<void> {
  await requestVoid(
    `/api/v1/conversations/${conversationId}/revert-to-message`,
    { method: "POST", body: { messageId } },
  );
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
  options: { deleteFromWdk?: boolean; cascade?: boolean } = {},
): Promise<void> {
  const query: Record<string, string> = {};
  if (options.deleteFromWdk === true) query["deleteFromWdk"] = "true";
  if (options.cascade === true) query["cascade"] = "true";
  await requestVoid(
    `/api/v1/conversations/${conversationId}`,
    Object.keys(query).length > 0
      ? { method: "DELETE", query }
      : { method: "DELETE" },
  );
}


export async function syncWdkConversations(
  siteId: string,
): Promise<Strategy[]> {
  const raw = await requestJson(
    conversationListSchema,
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
    openConversationResponseSchema,
    "/api/v1/conversations/open",
    { method: "POST", body: payload },
  );
  return raw;
}

export async function createConversation(args: {
  name: string;
  siteId: string;
  strategyAst: StrategyAst;
}): Promise<Strategy> {
  const raw = await requestJson(conversationResponseSchema, "/api/v1/conversations", {
    method: "POST",
    body: args,
  });
  return withDefaults(raw as Parameters<typeof withDefaults>[0]);
}

export async function updateConversation(
  conversationId: string,
  args: {
    name?: string;
    strategyAst?: StrategyAst | PlanArtifact;
    wdkStrategyId?: number | null;
    isSaved?: boolean;
  },
): Promise<Strategy> {
  const raw = await requestJson(
    conversationResponseSchema,
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
    strategyAst: StrategyAst;
    description?: string | null;
  },
): Promise<Strategy> {
  const raw = await requestJson(
    conversationResponseSchema,
    `/api/v1/conversations/${conversationId}/push`,
    { method: "POST", body: args },
  );
  return withDefaults(raw as Parameters<typeof withDefaults>[0]);
}

export async function computeStepCounts(
  siteId: string,
  strategyAst: StrategyAst,
): Promise<{ counts: Record<string, number | null> }> {
  return await requestJson(
    stepCountsResponseSchema,
    "/api/v1/conversations/step-counts",
    { method: "POST", body: { siteId, strategyAst } },
  );
}

export type { ConversationResponse };
