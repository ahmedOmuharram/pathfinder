import type { GeneSearchResponse, GeneResolveResponse } from "@pathfinder/shared";
import { requestJsonValidated } from "./http";
import {
  GeneResolveResponseSchema,
  GeneSearchResponseSchema,
  OrganismListResponseSchema,
} from "./schemas/gene";

export async function listOrganisms(siteId: string): Promise<string[]> {
  const resp = await requestJsonValidated(
    OrganismListResponseSchema,
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
  return (await requestJsonValidated(
    GeneSearchResponseSchema,
    `/api/v1/sites/${encodeURIComponent(siteId)}/genes/search`,
    { query: params },
  )) as GeneSearchResponse;
}

export async function resolveGeneIds(
  siteId: string,
  geneIds: string[],
): Promise<GeneResolveResponse> {
  return (await requestJsonValidated(
    GeneResolveResponseSchema,
    `/api/v1/sites/${encodeURIComponent(siteId)}/genes/resolve`,
    { method: "POST", body: { geneIds } },
  )) as GeneResolveResponse;
}
