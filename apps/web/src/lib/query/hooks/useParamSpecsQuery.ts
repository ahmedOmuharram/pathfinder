import { useQuery } from "@tanstack/react-query";
import { paramSpecsOptions } from "@/lib/api/sites";

export function useParamSpecsQuery(
  siteId: string,
  recordType: string,
  searchName: string,
) {
  return useQuery(paramSpecsOptions(siteId, recordType, searchName));
}
