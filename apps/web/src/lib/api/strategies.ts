import type { StrategyPlan, Strategy } from "@pathfinder/shared";
import { APIError, requestJson, requestJsonValidated } from "./http";
import {
  NormalizePlanResponseSchema,
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
  const raw = await requestJsonValidated(
    StrategyListItemListSchema,
    "/api/v1/strategies",
    { query: siteId ? { siteId } : undefined },
  );
  return raw.map((s) => withDefaults(s as Parameters<typeof withDefaults>[0]));
}

/**
 * Batch-sync all WDK strategies into the local DB and return the
 * summary list for this site.
 */
export async function syncWdkStrategies(siteId: string): Promise<Strategy[]> {
  const raw = await requestJsonValidated(
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
  return await requestJsonValidated(
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
  const raw = await requestJsonValidated(
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
  const raw = await requestJsonValidated(StrategySchema, "/api/v1/strategies", {
    method: "POST",
    body: args,
  });
  return withDefaults(raw as Parameters<typeof withDefaults>[0]);
}

export async function updateStrategy(
  strategyId: string,
  args: {
    name?: string;
    plan?: StrategyPlan;
    wdkStrategyId?: number | null;
    isSaved?: boolean;
  },
): Promise<Strategy> {
  const raw = await requestJsonValidated(
    StrategySchema,
    `/api/v1/strategies/${strategyId}`,
    {
      method: "PATCH",
      body: args,
    },
  );
  return withDefaults(raw as Parameters<typeof withDefaults>[0]);
}

export async function deleteStrategy(
  strategyId: string,
  deleteFromWdk?: boolean,
): Promise<void> {
  await requestJson<void>(`/api/v1/strategies/${strategyId}`, {
    method: "DELETE",
    query: deleteFromWdk ? { deleteFromWdk: "true" } : undefined,
  });
}

export async function normalizePlan(
  siteId: string,
  plan: StrategyPlan,
): Promise<{ plan: StrategyPlan; warnings?: unknown[] | null }> {
  const raw = await requestJsonValidated(
    NormalizePlanResponseSchema,
    "/api/v1/strategies/plan/normalize",
    { method: "POST", body: { siteId, plan } },
  );
  return raw as { plan: StrategyPlan; warnings?: unknown[] | null };
}

export async function restoreStrategy(strategyId: string): Promise<Strategy> {
  const raw = await requestJson<Record<string, unknown>>(
    `/api/v1/strategies/${strategyId}/restore`,
    { method: "POST" },
  );
  return withDefaults(raw as Parameters<typeof withDefaults>[0]);
}

export async function listDismissedStrategies(siteId: string): Promise<Strategy[]> {
  const raw = await requestJson<Record<string, unknown>[]>(
    "/api/v1/strategies/dismissed",
    { query: { siteId } },
  );
  return raw.map((s) => withDefaults(s as Parameters<typeof withDefaults>[0]));
}

export async function computeStepCounts(
  siteId: string,
  plan: StrategyPlan,
): Promise<{ counts: Record<string, number | null> }> {
  return await requestJsonValidated(
    StepCountsResponseSchema,
    "/api/v1/strategies/step-counts",
    { method: "POST", body: { siteId, plan } },
  );
}
