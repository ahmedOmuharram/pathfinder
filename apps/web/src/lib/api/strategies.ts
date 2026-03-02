import type { StrategyPlan, StrategyWithMeta } from "@pathfinder/shared";
import { APIError, requestJson } from "./http";

export async function listStrategies(
  siteId?: string | null,
): Promise<StrategyWithMeta[]> {
  return await requestJson<StrategyWithMeta[]>("/api/v1/strategies", {
    query: siteId ? { siteId } : undefined,
  });
}

/**
 * Batch-sync all WDK strategies into the local DB and return the full
 * local strategy list for this site.  Replaces the old
 * ``listWdkStrategies`` + ``listStrategies`` two-call pattern.
 */
export async function syncWdkStrategies(siteId: string): Promise<StrategyWithMeta[]> {
  return await requestJson<StrategyWithMeta[]>("/api/v1/strategies/sync-wdk", {
    method: "POST",
    query: { siteId },
  });
}

export async function openStrategy(payload: {
  siteId?: string;
  strategyId?: string;
  wdkStrategyId?: number;
}): Promise<{ strategyId: string }> {
  return await requestJson<{ strategyId: string }>("/api/v1/strategies/open", {
    method: "POST",
    body: payload,
  });
}

function looksLikeUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value,
  );
}

export async function getStrategy(strategyId: string): Promise<StrategyWithMeta> {
  // Some UI lists include synthetic IDs like "wdk:123". Make this failure explicit.
  if (!looksLikeUuid(strategyId)) {
    throw new APIError("Invalid strategy id.", {
      status: 400,
      statusText: "Bad Request",
      url: `/api/v1/strategies/${strategyId}`,
      data: { detail: "strategyId must be a UUID" },
    });
  }
  return await requestJson<StrategyWithMeta>(`/api/v1/strategies/${strategyId}`);
}

export async function createStrategy(args: {
  name: string;
  siteId: string;
  plan: StrategyPlan;
}): Promise<StrategyWithMeta> {
  return await requestJson<StrategyWithMeta>("/api/v1/strategies", {
    method: "POST",
    body: args,
  });
}

export async function updateStrategy(
  strategyId: string,
  args: {
    name?: string;
    plan?: StrategyPlan;
    wdkStrategyId?: number | null;
    isSaved?: boolean;
  },
): Promise<StrategyWithMeta> {
  return await requestJson<StrategyWithMeta>(`/api/v1/strategies/${strategyId}`, {
    method: "PATCH",
    body: args,
  });
}

export async function deleteStrategy(strategyId: string): Promise<void> {
  await requestJson<void>(`/api/v1/strategies/${strategyId}`, {
    method: "DELETE",
  });
}

export async function normalizePlan(
  siteId: string,
  plan: StrategyPlan,
): Promise<{ plan: StrategyPlan; warnings?: unknown[] | null }> {
  return await requestJson<{ plan: StrategyPlan; warnings?: unknown[] | null }>(
    "/api/v1/strategies/plan/normalize",
    { method: "POST", body: { siteId, plan } },
  );
}

export async function computeStepCounts(
  siteId: string,
  plan: StrategyPlan,
): Promise<{ counts: Record<string, number | null> }> {
  return await requestJson<{ counts: Record<string, number | null> }>(
    "/api/v1/strategies/step-counts",
    { method: "POST", body: { siteId, plan } },
  );
}
