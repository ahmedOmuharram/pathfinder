import type {
  ColocationParams,
  ConversationResponse,
  PlanArtifact,
  Step,
  Strategy,
  StrategyAst,
} from "@pathfinder/shared";
import { conversationResponseSchema } from "@pathfinder/shared/generated/zod/conversationResponseSchema";
import { openConversationResponseSchema } from "@pathfinder/shared/generated/zod/openConversationResponseSchema";
import { stepCountsResponseSchema } from "@pathfinder/shared/generated/zod/stepCountsResponseSchema";
import { stepResponseSchema } from "@pathfinder/shared/generated/zod/stepResponseSchema";
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

export type ConversationSummary = ConversationResponse;


export async function listConversations(
  siteId?: string | null,
): Promise<ConversationSummary[]> {
  return await requestJson(
    conversationListSchema,
    "/api/v1/conversations",
    siteId != null && siteId !== "" ? { query: { siteId } } : {},
  );
}

export async function listDismissedConversations(
  siteId?: string | null,
): Promise<ConversationSummary[]> {
  return await requestJson(
    conversationListSchema,
    "/api/v1/conversations/dismissed",
    siteId != null && siteId !== "" ? { query: { siteId } } : {},
  );
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

export function conversationDetailKey(conversationId: string) {
  return ["conversations", conversationId, "detail"] as const;
}

export function conversationDetailOptions(conversationId: string) {
  return queryOptions({
    queryKey: conversationDetailKey(conversationId),
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
    conversationResponseSchema,
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
    conversationResponseSchema,
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
    conversationResponseSchema,
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

const beginConversationResponseSchema = z.object({
  conversationId: z.uuid(),
  isNew: z.boolean(),
  name: z.string(),
});

export type BeginConversationResponse = z.infer<typeof beginConversationResponseSchema>;

export async function beginConversation(args: {
  conversationId: string;
  siteId: string;
  experimentId?: string | null;
  seedText?: string | null;
}): Promise<BeginConversationResponse> {
  const body: { siteId: string; experimentId?: string; seedText?: string } = {
    siteId: args.siteId,
  };
  if (args.experimentId != null && args.experimentId !== "")
    body.experimentId = args.experimentId;
  if (args.seedText != null && args.seedText !== "")
    body.seedText = args.seedText;
  return await requestJson(
    beginConversationResponseSchema,
    `/api/v1/conversations/${args.conversationId}/begin`,
    { method: "POST", body },
  );
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

export interface StepPatchArgs {
  parameters?: Record<string, unknown>;
  operator?: string;
  displayName?: string | null;
  colocationParams?: ColocationParams | null;
  wdkWeight?: number | null;
  searchName?: string;
}

export async function patchConversationStep(
  conversationId: string,
  stepId: string,
  args: StepPatchArgs,
  siteId: string,
): Promise<Step> {
  return await requestJson(
    stepResponseSchema,
    `/api/v1/conversations/${conversationId}/steps/${stepId}`,
    { method: "PATCH", body: args, query: { siteId } },
  );
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
