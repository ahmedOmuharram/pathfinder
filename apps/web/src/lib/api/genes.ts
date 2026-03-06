import type { GeneSearchResponse, GeneResolveResponse } from "@pathfinder/shared";
import { requestJson } from "./http";

/**
 * Re-exports from @pathfinder/shared for backward compatibility.
 * New code should import these types directly from "@pathfinder/shared".
 */
export type {
  GeneSearchResult,
  GeneSearchResponse,
  ResolvedGene,
  GeneResolveResponse,
} from "@pathfinder/shared";

export async function listOrganisms(siteId: string): Promise<string[]> {
  const resp = await requestJson<{ organisms: string[] }>(
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
  if (organism) params.organism = organism;
  if (offset > 0) params.offset = String(offset);
  return await requestJson<GeneSearchResponse>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/genes/search`,
    { query: params },
  );
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
