import { useQuery } from "@tanstack/react-query";
import { modelCatalogOptions } from "@/lib/api/models";

export function useModelCatalogQuery() {
  return useQuery(modelCatalogOptions());
}
