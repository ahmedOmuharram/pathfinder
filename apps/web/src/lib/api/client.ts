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
import type { StrategyWithMeta } from "@/features/strategy/types";
import { AppError } from "@/lib/errors/AppError";
import { APIError, requestJson } from "./http";

export { APIError };

// Sites / discovery

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

// Strategies

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

// Plan sessions

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

// VEuPathDB auth bridge — always authenticates against the portal

const AUTH_SITE_ID = "veupathdb";

export async function getVeupathdbAuthStatus(): Promise<{
  signedIn: boolean;
  name: string | null;
  email: string | null;
}> {
  return await requestJson(`/api/v1/veupathdb/auth/status`, {
    query: { siteId: AUTH_SITE_ID },
  });
}

export async function loginVeupathdb(
  email: string,
  password: string,
): Promise<{ success: boolean; authToken?: string }> {
  if (!email || !password) {
    throw new AppError("Email and password are required.", "INVARIANT_VIOLATION");
  }
  return await requestJson(`/api/v1/veupathdb/auth/login`, {
    method: "POST",
    query: { siteId: AUTH_SITE_ID },
    body: { email, password },
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

// Gene search

export interface GeneSearchResult {
  geneId: string;
  displayName: string;
  organism: string;
  product: string;
  matchedFields: string[];
  geneName?: string;
  geneType?: string;
  location?: string;
}

export interface GeneSearchResponse {
  results: GeneSearchResult[];
  totalCount: number;
  suggestedOrganisms?: string[];
}

export async function searchGenes(
  siteId: string,
  query: string,
  organism?: string | null,
  limit: number = 20,
  offset: number = 0,
): Promise<GeneSearchResponse> {
  const params: Record<string, string> = { q: query, limit: String(limit) };
  if (organism) params.organism = organism;
  if (offset > 0) params.offset = String(offset);
  return await requestJson<GeneSearchResponse>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/genes/search`,
    { query: params },
  );
}

export interface ResolvedGene {
  geneId: string;
  displayName: string;
  organism: string;
  product: string;
  geneName: string;
  geneType: string;
  location: string;
}

export interface GeneResolveResponse {
  resolved: ResolvedGene[];
  unresolved: string[];
}

export async function resolveGeneIds(
  siteId: string,
  geneIds: string[],
): Promise<GeneResolveResponse> {
  return await requestJson<GeneResolveResponse>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/genes/resolve`,
    { method: "POST", body: { geneIds } },
  );
}

// Models / catalog

export interface ModelCatalogResponse {
  models: import("@pathfinder/shared").ModelCatalogEntry[];
  default: string;
  defaultReasoningEffort: import("@pathfinder/shared").ReasoningEffort;
}

export async function listModels(): Promise<ModelCatalogResponse> {
  return await requestJson<ModelCatalogResponse>("/api/v1/models");
}
