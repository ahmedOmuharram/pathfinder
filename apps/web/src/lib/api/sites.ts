import type {
  ParamSpec,
  RecordType,
  Search,
  SearchValidationResponse,
  VEuPathDBSite,
} from "@pathfinder/shared";
import { requestJson } from "./http";

export async function listSites(): Promise<VEuPathDBSite[]> {
  return await requestJson<VEuPathDBSite[]>("/api/v1/sites");
}

export async function getRecordTypes(siteId: string): Promise<RecordType[]> {
  return await requestJson<RecordType[]>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/record-types`,
  );
}

export async function getSearches(
  siteId: string,
  recordType?: string | null,
): Promise<Search[]> {
  return await requestJson<Search[]>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/searches`,
    { query: recordType ? { recordType } : undefined },
  );
}

export async function getParamSpecs(
  siteId: string,
  recordType: string,
  searchName: string,
  contextValues: Record<string, unknown> = {},
): Promise<ParamSpec[]> {
  return await requestJson<ParamSpec[]>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/searches/${encodeURIComponent(
      recordType,
    )}/${encodeURIComponent(searchName)}/param-specs`,
    {
      method: "POST",
      body: { contextValues },
    },
  );
}

export async function validateSearchParams(
  siteId: string,
  recordType: string,
  searchName: string,
  contextValues: Record<string, unknown> = {},
): Promise<SearchValidationResponse> {
  return await requestJson<SearchValidationResponse>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/searches/${encodeURIComponent(
      recordType,
    )}/${encodeURIComponent(searchName)}/validate`,
    { method: "POST", body: { contextValues } },
  );
}
