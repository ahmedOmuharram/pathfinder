import { getQueryClient } from "@/lib/query/client";
import { strategiesListOptions } from "@/lib/api/strategies";
import type { Strategy } from "@pathfinder/shared";

/** Upsert a strategy into the TanStack Query list cache for its site. */
export function addStrategyToCache(item: Strategy): void {
  const qc = getQueryClient();
  qc.setQueryData(
    strategiesListOptions(item.siteId).queryKey,
    (old: Strategy[] | undefined) => {
      const prev = old ?? [];
      const existing = prev.find((c) => c.id === item.id);
      if (existing) {
        return prev.map((c) => (c.id === item.id ? { ...c, ...item } : c));
      }
      return [item, ...prev];
    },
  );
}
