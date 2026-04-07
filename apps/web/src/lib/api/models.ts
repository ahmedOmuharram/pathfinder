import { queryOptions } from "@tanstack/react-query";
import type { ModelCatalogEntry, ReasoningEffort } from "@pathfinder/shared";
import { requestJson } from "./http";
import { ModelCatalogResponseSchema } from "./schemas/model";

interface ModelCatalogResponse {
  models: ModelCatalogEntry[];
  default: string;
  defaultReasoningEffort: ReasoningEffort;
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
