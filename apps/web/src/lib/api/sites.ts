import type {
  ParamSpec,
  RecordType,
  Search,
  SearchValidationResponse,
  VEuPathDBSite,
} from "@pathfinder/shared";
import { requestJsonValidated } from "./http";
import {
  VEuPathDBSiteListSchema,
  ParamSpecListSchema,
  RecordTypeListSchema,
  SearchListSchema,
  SearchValidationResponseSchema,
} from "./schemas/site";
import type { StepParameters } from "@/lib/strategyGraph/types";

export async function listSites(): Promise<VEuPathDBSite[]> {
  return (await requestJsonValidated(
    VEuPathDBSiteListSchema,
    "/api/v1/sites",
  )) as VEuPathDBSite[];
}

export async function getRecordTypes(siteId: string): Promise<RecordType[]> {
  return (await requestJsonValidated(
    RecordTypeListSchema,
    `/api/v1/sites/${encodeURIComponent(siteId)}/record-types`,
  )) as RecordType[];
}

export async function getSearches(
  siteId: string,
  recordType?: string | null,
): Promise<Search[]> {
  return (await requestJsonValidated(
    SearchListSchema,
    `/api/v1/sites/${encodeURIComponent(siteId)}/searches`,
    recordType != null && recordType !== "" ? { query: { recordType } } : {},
  )) as Search[];
}

export async function getParamSpecs(
  siteId: string,
  recordType: string,
  searchName: string,
  contextValues: StepParameters = {},
): Promise<ParamSpec[]> {
  return (await requestJsonValidated(
    ParamSpecListSchema,
    `/api/v1/sites/${encodeURIComponent(siteId)}/searches/${encodeURIComponent(
      recordType,
    )}/${encodeURIComponent(searchName)}/param-specs`,
    {
      method: "POST",
      body: { contextValues },
    },
  )) as ParamSpec[];
}

export async function validateSearchParams(
  siteId: string,
  recordType: string,
  searchName: string,
  contextValues: StepParameters = {},
): Promise<SearchValidationResponse> {
  return (await requestJsonValidated(
    SearchValidationResponseSchema,
    `/api/v1/sites/${encodeURIComponent(siteId)}/searches/${encodeURIComponent(
      recordType,
    )}/${encodeURIComponent(searchName)}/validate`,
    { method: "POST", body: { contextValues } },
  )) as SearchValidationResponse;
}
