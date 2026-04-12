import { queryOptions } from "@tanstack/react-query";
import type { StrategyPlan, Strategy, PlanningArtifact } from "@pathfinder/shared";
import { z } from "zod";
import { APIError, requestJson, requestVoid } from "./http";
import {
  OpenStrategyResponseSchema,
  StepCountsResponseSchema,
  StrategyListItemListSchema,
  StrategySchema,
} from "./schemas/strategy";

/**
 * The list endpoints return objects without `steps` / `rootStepId`.
 * Fill in safe defaults so they conform to the full `Strategy` shape.
 */
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

export async function listStrategies(siteId?: string | null): Promise<Strategy[]> {
  const raw = await requestJson(
    StrategyListItemListSchema,
    "/api/v1/strategies",
    siteId != null && siteId !== "" ? { query: { siteId } } : {},
  );
  return raw.map((s) => withDefaults(s as Parameters<typeof withDefaults>[0]));
}

/**
 * Batch-sync all WDK strategies into the local DB and return the
 * summary list for this site.
 */
export async function syncWdkStrategies(siteId: string): Promise<Strategy[]> {
  const raw = await requestJson(
    StrategyListItemListSchema,
    "/api/v1/strategies/sync-wdk",
    { method: "POST", query: { siteId } },
  );
  return raw.map((s) => withDefaults(s as Parameters<typeof withDefaults>[0]));
}

export async function openStrategy(payload: {
  siteId?: string;
  strategyId?: string;
  wdkStrategyId?: number;
}): Promise<{ strategyId: string }> {
  return await requestJson(
    OpenStrategyResponseSchema,
    "/api/v1/strategies/open",
    { method: "POST", body: payload },
  );
}

function looksLikeUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value,
  );
}

export async function getStrategy(strategyId: string): Promise<Strategy> {
  // Some UI lists include synthetic IDs like "wdk:123". Make this failure explicit.
  if (!looksLikeUuid(strategyId)) {
    throw new APIError("Invalid strategy id.", {
      status: 400,
      statusText: "Bad Request",
      url: `/api/v1/strategies/${strategyId}`,
      data: { detail: "strategyId must be a UUID" },
    });
  }
  const raw = await requestJson(
    StrategySchema,
    `/api/v1/strategies/${strategyId}`,
  );
  return withDefaults(raw as Parameters<typeof withDefaults>[0]);
}

export async function createStrategy(args: {
  name: string;
  siteId: string;
  plan: StrategyPlan;
}): Promise<Strategy> {
  const raw = await requestJson(StrategySchema, "/api/v1/strategies", {
    method: "POST",
    body: args,
  });
  return withDefaults(raw as Parameters<typeof withDefaults>[0]);
}

export async function updateStrategy(
  strategyId: string,
  args: {
    name?: string;
    plan?: StrategyPlan | NonNullable<PlanningArtifact["proposedStrategyPlan"]>;
    wdkStrategyId?: number | null;
    isSaved?: boolean;
  },
): Promise<Strategy> {
  const raw = await requestJson(
    StrategySchema,
    `/api/v1/strategies/${strategyId}`,
    {
      method: "PATCH",
      body: args,
    },
  );
  return withDefaults(raw as Parameters<typeof withDefaults>[0]);
}

export async function pushStrategy(
  strategyId: string,
  args: {
    name: string;
    siteId: string;
    plan: StrategyPlan;
    description?: string | null;
  },
): Promise<Strategy> {
  const raw = await requestJson(
    StrategySchema,
    `/api/v1/strategies/${strategyId}/push`,
    {
      method: "POST",
      body: args,
    },
  );
  return withDefaults(raw as Parameters<typeof withDefaults>[0]);
}

export async function deleteStrategy(
  strategyId: string,
  deleteFromWdk?: boolean,
): Promise<void> {
  await requestVoid(
    `/api/v1/strategies/${strategyId}`,
    deleteFromWdk === true
      ? { method: "DELETE", query: { deleteFromWdk: "true" } }
      : { method: "DELETE" },
  );
}

export async function restoreStrategy(strategyId: string): Promise<Strategy> {
  const raw = await requestJson(
    StrategySchema,
    `/api/v1/strategies/${strategyId}/restore`,
    { method: "POST" },
  );
  return withDefaults(raw as Parameters<typeof withDefaults>[0]);
}

export async function listDismissedStrategies(siteId: string): Promise<Strategy[]> {
  const raw = await requestJson(
    StrategyListItemListSchema,
    "/api/v1/strategies/dismissed",
    { query: { siteId } },
  );
  return raw.map((s) => withDefaults(s as Parameters<typeof withDefaults>[0]));
}

export async function computeStepCounts(
  siteId: string,
  plan: StrategyPlan,
): Promise<{ counts: Record<string, number | null> }> {
  return await requestJson(
    StepCountsResponseSchema,
    "/api/v1/strategies/step-counts",
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

export function strategiesListOptions(siteId: string) {
  return queryOptions({
    queryKey: ["strategies", "list", siteId] as const,
    queryFn: () => syncWdkStrategies(siteId),
  });
}

export function dismissedStrategiesOptions(siteId: string) {
  return queryOptions({
    queryKey: ["strategies", "dismissed", siteId] as const,
    queryFn: () => listDismissedStrategies(siteId),
  });
}
