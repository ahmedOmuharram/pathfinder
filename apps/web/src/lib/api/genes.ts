import { queryOptions } from "@tanstack/react-query";
import type { GeneSearchResponse, GeneResolveResponse } from "@pathfinder/shared";
import { geneResolveResponseSchema } from "@pathfinder/shared/generated/zod/geneResolveResponseSchema";
import { geneSearchResponseSchema } from "@pathfinder/shared/generated/zod/geneSearchResponseSchema";
import { organismsResponseSchema } from "@pathfinder/shared/generated/zod/organismsResponseSchema";

import { requestJson } from "./http";

export async function listOrganisms(siteId: string): Promise<string[]> {
  const resp = await requestJson(
    organismsResponseSchema,
    `/api/v1/sites/${encodeURIComponent(siteId)}/organisms`,
  );
  return resp.organisms;
}

export async function searchGenes(
  siteId: string,
  query: string,
  organism?: string | null,
  limit: number = 20,
  offset: number = 0,
): Promise<GeneSearchResponse> {
  const params: Record<string, string> = { q: query, limit: String(limit) };
  if (organism != null && organism !== "") params["organism"] = organism;
  if (offset > 0) params["offset"] = String(offset);
  return (await requestJson(
    geneSearchResponseSchema,
    `/api/v1/sites/${encodeURIComponent(siteId)}/genes/search`,
    { query: params },
  ));
}

export async function resolveGeneIds(
  siteId: string,
  geneIds: string[],
): Promise<GeneResolveResponse> {
  return (await requestJson(
    geneResolveResponseSchema,
    `/api/v1/sites/${encodeURIComponent(siteId)}/genes/resolve`,
    { method: "POST", body: { geneIds } },
  ));
}

export function organismsOptions(siteId: string) {
  return queryOptions({
    queryKey: ["genes", "organisms", siteId] as const,
    queryFn: () => listOrganisms(siteId),
    staleTime: 5 * 60_000,
    enabled: siteId !== "",
  });
}
