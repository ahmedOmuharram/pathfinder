import { queryOptions } from "@tanstack/react-query";
import { modelListResponseSchema } from "@pathfinder/shared/generated/zod/modelListResponseSchema";
import type { ModelListResponse } from "@pathfinder/shared/generated/types/ModelListResponse";

import { requestJson } from "./http";

export type ModelCatalogResponse = ModelListResponse;

export async function listModels(): Promise<ModelCatalogResponse> {
  return await requestJson(modelListResponseSchema, "/api/v1/models");
}

export function modelCatalogOptions() {
  return queryOptions({
    queryKey: ["models", "catalog"] as const,
    queryFn: listModels,
    staleTime: Infinity,
  });
}
