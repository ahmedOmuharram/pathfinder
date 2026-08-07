import { useQuery } from "@tanstack/react-query";
import { listTiersQueryOptions } from "@pathfinder/shared/generated/hooks/useListTiers";

export function useTierPresetsQuery() {
  return useQuery(listTiersQueryOptions());
}
