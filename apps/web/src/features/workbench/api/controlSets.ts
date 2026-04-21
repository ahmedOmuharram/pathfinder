import { queryOptions } from "@tanstack/react-query";
import type { ControlSet } from "@pathfinder/shared";
import { controlSetResponseSchema } from "@pathfinder/shared/generated/zod/controlSetResponseSchema";
import { z } from "zod";

import { requestBlob, requestJson, requestVoid } from "@/lib/api/http";

const ControlSetListSchema = z.array(controlSetResponseSchema);

export async function listControlSets(siteId: string): Promise<ControlSet[]> {
  return (await requestJson(ControlSetListSchema, "/api/v1/control-sets", {
    query: { siteId },
  }));
}

export function controlSetsOptions(siteId: string) {
  return queryOptions({
    queryKey: ["control-sets", "list", siteId] as const,
    queryFn: () => listControlSets(siteId),
    staleTime: 30_000,
    enabled: siteId !== "",
  });
}

export async function getControlSet(id: string): Promise<ControlSet> {
  return (await requestJson(controlSetResponseSchema, `/api/v1/control-sets/${id}`));
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
  return (await requestJson(controlSetResponseSchema, "/api/v1/control-sets", {
    method: "POST",
    body,
  }));
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
