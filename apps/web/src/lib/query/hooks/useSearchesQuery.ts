import { useQuery } from "@tanstack/react-query";
import { searchesOptions } from "@/lib/api/sites";

export function useSearchesQuery(siteId: string, recordType?: string | null) {
  return useQuery(searchesOptions(siteId, recordType));
}
