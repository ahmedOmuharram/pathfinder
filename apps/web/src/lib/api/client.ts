import type {
  ParamSpec,
  PlanSession,
  PlanSessionSummary,
  RecordType,
  Search,
  SearchValidationResponse,
  StrategyPlan,
  VEuPathDBSite,
} from "@pathfinder/shared";
import type { StrategyWithMeta } from "@/types/strategy";
import { AppError } from "@/shared/errors/AppError";
import { APIError, requestJson } from "./http";

export { APIError };

// -----------------------------------------------------------------------------
// Sites / discovery
// -----------------------------------------------------------------------------

export async function listSites(): Promise<VEuPathDBSite[]> {
  return await requestJson<VEuPathDBSite[]>("/api/v1/sites");
}

export async function getRecordTypes(siteId: string): Promise<RecordType[]> {
  return await requestJson<RecordType[]>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/record-types`,
  );
}

export async function getSearches(
  siteId: string,
  recordType?: string | null,
): Promise<Search[]> {
  return await requestJson<Search[]>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/searches`,
    { query: recordType ? { recordType } : undefined },
  );
}

export async function getParamSpecs(
  siteId: string,
  recordType: string,
  searchName: string,
  contextValues: Record<string, unknown> = {},
): Promise<ParamSpec[]> {
  return await requestJson<ParamSpec[]>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/searches/${encodeURIComponent(
      recordType,
    )}/${encodeURIComponent(searchName)}/param-specs`,
    {
      method: "POST",
      body: { contextValues },
    },
  );
}

export async function validateSearchParams(
  siteId: string,
  recordType: string,
  searchName: string,
  contextValues: Record<string, unknown> = {},
): Promise<SearchValidationResponse> {
  return await requestJson<SearchValidationResponse>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/searches/${encodeURIComponent(
      recordType,
    )}/${encodeURIComponent(searchName)}/validate`,
    { method: "POST", body: { contextValues } },
  );
}

// -----------------------------------------------------------------------------
// Strategies
// -----------------------------------------------------------------------------

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

// -----------------------------------------------------------------------------
// Plan sessions
// -----------------------------------------------------------------------------

export async function listPlans(siteId?: string | null): Promise<PlanSessionSummary[]> {
  return await requestJson<PlanSessionSummary[]>("/api/v1/plans", {
    query: siteId ? { siteId } : undefined,
  });
}

export async function openPlanSession(args: {
  siteId: string;
  title?: string | null;
  planSessionId?: string | null;
}): Promise<{ planSessionId: string }> {
  return await requestJson<{ planSessionId: string }>("/api/v1/plans/open", {
    method: "POST",
    body: args,
  });
}

export async function getPlanSession(planSessionId: string): Promise<PlanSession> {
  return await requestJson<PlanSession>(`/api/v1/plans/${planSessionId}`);
}

export async function updatePlanSession(
  planSessionId: string,
  args: { title: string },
): Promise<PlanSessionSummary> {
  return await requestJson<PlanSessionSummary>(`/api/v1/plans/${planSessionId}`, {
    method: "PATCH",
    body: args,
  });
}

export async function deletePlanSession(
  planSessionId: string,
): Promise<{ success: boolean }> {
  return await requestJson<{ success: boolean }>(`/api/v1/plans/${planSessionId}`, {
    method: "DELETE",
  });
}

// -----------------------------------------------------------------------------
// VEuPathDB auth bridge
// -----------------------------------------------------------------------------

export async function getVeupathdbAuthStatus(siteId: string): Promise<{
  signedIn: boolean;
  name: string | null;
  email: string | null;
}> {
  return await requestJson(`/api/v1/veupathdb/auth/status`, { query: { siteId } });
}

export async function loginVeupathdb(
  siteId: string,
  email: string,
  password: string,
  redirectTo?: string | null,
): Promise<{ success: boolean; authToken?: string }>;
export async function loginVeupathdb(args: {
  siteId: string;
  email: string;
  password: string;
  redirectTo?: string | null;
}): Promise<{ success: boolean; authToken?: string }>;
export async function loginVeupathdb(
  siteIdOrArgs:
    | string
    | { siteId: string; email: string; password: string; redirectTo?: string | null },
  email?: string,
  password?: string,
  redirectTo?: string | null,
): Promise<{ success: boolean; authToken?: string }> {
  const normalized =
    typeof siteIdOrArgs === "string"
      ? {
          siteId: siteIdOrArgs,
          email: email ?? "",
          password: password ?? "",
          redirectTo,
        }
      : siteIdOrArgs;

  if (!normalized.email || !normalized.password) {
    throw new AppError("Email and password are required.", "INVARIANT_VIOLATION");
  }
  return await requestJson(`/api/v1/veupathdb/auth/login`, {
    method: "POST",
    query: {
      siteId: normalized.siteId,
      redirectTo: normalized.redirectTo ?? undefined,
    },
    body: {
      email: normalized.email,
      password: normalized.password,
    },
  });
}

export async function setVeupathdbToken(
  token: string,
): Promise<{ success: boolean; authToken?: string }> {
  return await requestJson(`/api/v1/veupathdb/auth/token`, {
    method: "POST",
    body: { token },
  });
}

export async function logoutVeupathdb(): Promise<{ success: boolean }> {
  return await requestJson(`/api/v1/veupathdb/auth/logout`, { method: "POST" });
}

/**
 * Re-derive the internal ``pathfinder-auth`` token from a live VEuPathDB session.
 * Called on page load when the internal token is missing/expired.
 */
export async function refreshAuth(): Promise<{ success: boolean; authToken?: string }> {
  return await requestJson(`/api/v1/veupathdb/auth/refresh`, { method: "POST" });
}

// -----------------------------------------------------------------------------
// Models / catalog
// -----------------------------------------------------------------------------

export interface ModelCatalogResponse {
  models: import("@pathfinder/shared").ModelCatalogEntry[];
  defaults: { execute: string; plan: string };
}

export async function listModels(): Promise<ModelCatalogResponse> {
  return await requestJson<ModelCatalogResponse>("/api/v1/models");
}
