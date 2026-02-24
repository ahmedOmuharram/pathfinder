import type { Experiment, ExperimentSummary } from "@pathfinder/shared";
import { buildUrl, requestJson } from "@/lib/api/http";

export interface RecordAttribute {
  name: string;
  displayName: string;
  help?: string | null;
  type?: string | null;
  isDisplayable?: boolean;
}

export interface WdkRecord {
  id: { name: string; value: string }[];
  attributes: Record<string, string | null>;
  _classification?: "TP" | "FP" | "FN" | "TN" | null;
}

export interface RecordsResponse {
  records: WdkRecord[];
  meta: {
    totalCount: number;
    displayTotalCount: number;
    responseCount: number;
    pagination: { offset: number; numRecords: number };
    attributes: string[];
    tables: string[];
  };
}

export interface StrategyNode {
  stepId: number;
  primaryInput?: StrategyNode;
  secondaryInput?: StrategyNode;
}

export interface StrategyResponse {
  strategyId: number;
  name: string;
  stepTree: StrategyNode;
  steps: Record<
    string,
    {
      stepId: number;
      searchName: string;
      customName?: string;
      estimatedSize?: number;
      searchConfig?: { parameters: Record<string, string> };
    }
  >;
}

export async function listExperiments(
  siteId?: string | null,
): Promise<ExperimentSummary[]> {
  return await requestJson<ExperimentSummary[]>("/api/v1/experiments", {
    query: siteId ? { siteId } : undefined,
  });
}

export async function getExperiment(experimentId: string): Promise<Experiment> {
  return await requestJson<Experiment>(`/api/v1/experiments/${experimentId}`);
}

export async function deleteExperiment(experimentId: string): Promise<void> {
  await requestJson(`/api/v1/experiments/${experimentId}`, { method: "DELETE" });
}

export async function updateExperimentNotes(
  experimentId: string,
  notes: string,
): Promise<Experiment> {
  return await requestJson<Experiment>(`/api/v1/experiments/${experimentId}`, {
    method: "PATCH",
    body: { notes },
  });
}

export async function exportExperiment(
  experimentId: string,
  name: string,
): Promise<void> {
  const url = buildUrl(`/api/v1/experiments/${experimentId}/export`);
  const resp = await fetch(url, { credentials: "include" });
  if (!resp.ok) throw new Error(`Export failed: ${resp.status}`);
  const blob = await resp.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${name.replace(/\s+/g, "_").slice(0, 50)}.zip`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export async function getExperimentAttributes(
  experimentId: string,
): Promise<{ attributes: RecordAttribute[]; recordType: string }> {
  return await requestJson(`/api/v1/experiments/${experimentId}/results/attributes`);
}

export async function getExperimentRecords(
  experimentId: string,
  opts?: {
    offset?: number;
    limit?: number;
    sort?: string;
    dir?: "ASC" | "DESC";
    attributes?: string[];
  },
): Promise<RecordsResponse> {
  const query: Record<string, string> = {};
  if (opts?.offset != null) query.offset = String(opts.offset);
  if (opts?.limit != null) query.limit = String(opts.limit);
  if (opts?.sort) query.sort = opts.sort;
  if (opts?.dir) query.dir = opts.dir;
  if (opts?.attributes?.length) query.attributes = opts.attributes.join(",");
  return await requestJson<RecordsResponse>(
    `/api/v1/experiments/${experimentId}/results/records`,
    { query },
  );
}

export async function getExperimentRecordDetail(
  experimentId: string,
  primaryKey: { name: string; value: string }[],
): Promise<Record<string, unknown>> {
  return await requestJson(`/api/v1/experiments/${experimentId}/results/record`, {
    method: "POST",
    body: { primaryKey },
  });
}

export async function getExperimentStrategy(
  experimentId: string,
): Promise<StrategyResponse> {
  return await requestJson<StrategyResponse>(
    `/api/v1/experiments/${experimentId}/strategy`,
  );
}

export async function getExperimentDistribution(
  experimentId: string,
  attributeName: string,
): Promise<Record<string, unknown>> {
  return await requestJson(
    `/api/v1/experiments/${experimentId}/results/distributions/${encodeURIComponent(attributeName)}`,
  );
}

export async function getExperimentAnalysisTypes(
  experimentId: string,
): Promise<{ analysisTypes: Record<string, unknown>[] }> {
  return await requestJson(`/api/v1/experiments/${experimentId}/analyses/types`);
}

export async function runExperimentAnalysis(
  experimentId: string,
  analysisName: string,
  parameters: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return await requestJson(`/api/v1/experiments/${experimentId}/analyses/run`, {
    method: "POST",
    body: { analysisName, parameters },
  });
}

export async function refineExperiment(
  experimentId: string,
  action: "combine" | "transform",
  config: Record<string, unknown>,
): Promise<{ success: boolean; newStepId?: number }> {
  return await requestJson(`/api/v1/experiments/${experimentId}/refine`, {
    method: "POST",
    body: { action, ...config },
  });
}

export async function reEvaluateExperiment(experimentId: string): Promise<Experiment> {
  return await requestJson<Experiment>(
    `/api/v1/experiments/${experimentId}/re-evaluate`,
    { method: "POST" },
  );
}
