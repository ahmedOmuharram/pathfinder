import { requestJson } from "./http";

export interface ModelCatalogResponse {
  models: import("@pathfinder/shared").ModelCatalogEntry[];
  default: string;
  defaultReasoningEffort: import("@pathfinder/shared").ReasoningEffort;
}

export async function listModels(): Promise<ModelCatalogResponse> {
  return await requestJson<ModelCatalogResponse>("/api/v1/models");
}
