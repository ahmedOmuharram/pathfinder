import type { ApiClient } from "../../fixtures/api-client";
import { leafBySearch } from "../../fixtures/ast";

/**
 * The organism bound on a thread's taxon leaf.
 *
 * A branch and a revert both have to reproduce a strategy's parameter values,
 * not only its shape, so the specs read the value the leaf actually carries.
 */
export async function taxonOrganism(
  api: ApiClient,
  conversationId: string,
): Promise<unknown[]> {
  const leaf = await leafBySearch(
    await api.get(`/api/v1/conversations/${conversationId}/ast`),
    "GenesByTaxon",
  );
  return leaf.parameters?.["organism"]?.values ?? [];
}
