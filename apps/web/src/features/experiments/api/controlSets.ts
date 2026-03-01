import type { ControlSet } from "@pathfinder/shared";
import { requestJson } from "@/lib/api/http";

export async function listControlSets(siteId: string): Promise<ControlSet[]> {
  return await requestJson<ControlSet[]>("/api/v1/control-sets", {
    query: { siteId },
  });
}

export async function getControlSet(id: string): Promise<ControlSet> {
  return await requestJson<ControlSet>(`/api/v1/control-sets/${id}`);
}

export async function createControlSet(body: {
  name: string;
  siteId: string;
  recordType: string;
  positiveIds: string[];
  negativeIds: string[];
  source?: string;
  tags?: string[];
  provenanceNotes?: string;
  isPublic?: boolean;
}): Promise<ControlSet> {
  return await requestJson<ControlSet>("/api/v1/control-sets", {
    method: "POST",
    body,
  });
}

export async function deleteControlSet(id: string): Promise<void> {
  await requestJson(`/api/v1/control-sets/${id}`, { method: "DELETE" });
}

export async function getExperimentReport(experimentId: string): Promise<void> {
  const resp = await fetch(`/api/v1/experiments/${experimentId}/report`, {
    credentials: "include",
  });
  if (!resp.ok) throw new Error(`Report generation failed: ${resp.status}`);
  const blob = await resp.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `experiment-report.html`;
  a.click();
  URL.revokeObjectURL(a.href);
}
