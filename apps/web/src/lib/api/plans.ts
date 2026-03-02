import type { PlanSession, PlanSessionSummary } from "@pathfinder/shared";
import { requestJson } from "./http";

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
