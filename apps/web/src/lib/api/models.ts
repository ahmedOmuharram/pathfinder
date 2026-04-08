import { queryOptions } from "@tanstack/react-query";
import type { ModelCatalogEntry, ModelProvider, TierName } from "@pathfinder/shared";
import { requestJson } from "./http";
import { ModelCatalogResponseSchema } from "./schemas/model";

export interface ModelCatalogResponse {
  models: ModelCatalogEntry[];
  defaultProvider: ModelProvider;
  defaultTier: TierName;
}

export async function listModels(): Promise<ModelCatalogResponse> {
  return (await requestJson(
    ModelCatalogResponseSchema,
    "/api/v1/models",
  )) as ModelCatalogResponse;
}

export function modelCatalogOptions() {
  return queryOptions({
    queryKey: ["models", "catalog"] as const,
    queryFn: listModels,
    staleTime: Infinity,
  });
}
