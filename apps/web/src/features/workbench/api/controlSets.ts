import type { ControlSet } from "@pathfinder/shared";
import { requestBlob, requestJson, requestVoid } from "@/lib/api/http";
import { ControlSetSchema, ControlSetListSchema } from "@/lib/api/schemas/control-set";

export async function listControlSets(siteId: string): Promise<ControlSet[]> {
  return (await requestJson(ControlSetListSchema, "/api/v1/control-sets", {
    query: { siteId },
  })) as ControlSet[];
}

export async function getControlSet(id: string): Promise<ControlSet> {
  return (await requestJson(ControlSetSchema, `/api/v1/control-sets/${id}`)) as ControlSet;
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
  return (await requestJson(ControlSetSchema, "/api/v1/control-sets", {
    method: "POST",
    body,
  })) as ControlSet;
}

export async function deleteControlSet(id: string): Promise<void> {
  await requestVoid(`/api/v1/control-sets/${id}`, { method: "DELETE" });
}

export async function getExperimentReport(experimentId: string): Promise<void> {
  const blob = await requestBlob(`/api/v1/experiments/${experimentId}/export`);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `experiment-report.html`;
  a.click();
  URL.revokeObjectURL(a.href);
}
