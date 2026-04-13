/**
 * Shared experiment API functions -- used by both workbench and chat features.
 */

import { queryOptions } from "@tanstack/react-query";
import type { ExperimentSummary } from "@pathfinder/shared";
import { buildUrl, requestJson } from "@/lib/api/http";
import { streamTypedEvents } from "@/lib/sse/typedEventStream";
import { ExperimentSummaryListSchema } from "./schemas/experiment";

/** List experiments, optionally filtered by site. */
export async function listExperiments(
  siteId?: string | null,
): Promise<ExperimentSummary[]> {
  return (await requestJson(
    ExperimentSummaryListSchema,
    "/api/v1/experiments",
    siteId != null && siteId !== "" ? { query: { siteId } } : {},
  )) as ExperimentSummary[];
}

export function experimentsListOptions(siteId: string) {
  return queryOptions({
    queryKey: ["experiments", "list", siteId] as const,
    queryFn: () => listExperiments(siteId),
    staleTime: 30_000,
    enabled: siteId !== "",
  });
}

/**
 * Shape of each decoded event from the `/api/v1/experiments/seed` SSE stream.
 *
 * The backend emits typed Pydantic models (``SeedProgress`` / ``SeedStrategyComplete``
 * / ``SeedItemError`` / ``SeedComplete``) — every variant includes a ``message``
 * field, which is all this UI surface needs.
 */
interface SeedStreamEvent {
  type: string;
  message: string;
}

/**
 * Seed demo strategies via SSE.  Calls `onMessage` for each progress event
 * and resolves when the stream emits `[DONE]`.
 */
export async function seedExperiments(
  onMessage: (message: string) => void,
  siteId?: string,
): Promise<void> {
  const params = siteId != null && siteId !== "" ? `?site_id=${siteId}` : "";
  const url = buildUrl(`/api/v1/experiments/seed${params}`);

  for await (const event of streamTypedEvents<SeedStreamEvent>(url, {
    method: "POST",
  })) {
    onMessage(event.message);
  }
}
