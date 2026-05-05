import { useQuery } from "@tanstack/react-query";
import { listModelsQueryOptions } from "@pathfinder/shared/generated/hooks/useListModels";

export function useModelCatalogQuery() {
  return useQuery(listModelsQueryOptions());
}
