import type { Experiment, ExperimentSummary } from "@pathfinder/shared";
import { buildUrl, requestJson } from "@/lib/api/http";

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
