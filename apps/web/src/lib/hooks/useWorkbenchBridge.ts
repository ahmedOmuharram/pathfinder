"use client";

import { useInvalidateGeneSets } from "@/lib/query/hooks/useInvalidateGeneSets";

/**
 * Bridge between chat events and the gene-set query cache.
 *
 * When the backend emits a gene-set event during streaming, this hook
 * invalidates the TanStack Query cache so the list refetches.
 */
export function useWorkbenchBridge() {
  const invalidateGeneSets = useInvalidateGeneSets();

  const handleWorkbenchGeneSet = (_gs: {
    id: string;
    name: string;
    geneCount: number;
    source: string;
    siteId: string;
  }) => {
    void invalidateGeneSets();
  };

  return { handleWorkbenchGeneSet };
}
