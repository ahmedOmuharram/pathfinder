import type { ModelCatalogEntry, ReasoningEffort } from "@pathfinder/shared";
import { requestJsonValidated } from "./http";
import { ModelCatalogResponseSchema } from "./schemas/model";

interface ModelCatalogResponse {
  models: ModelCatalogEntry[];
  default: string;
  defaultReasoningEffort: ReasoningEffort;
}

export async function listModels(): Promise<ModelCatalogResponse> {
  return (await requestJsonValidated(
    ModelCatalogResponseSchema,
    "/api/v1/models",
  )) as ModelCatalogResponse;
}
