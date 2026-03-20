import type { Experiment } from "@pathfinder/shared";
import { requestBlob, requestJson } from "@/lib/api/http";
import type { StepParameters } from "@/lib/strategyGraph/types";

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
  const blob = await requestBlob(`/api/v1/experiments/${experimentId}/export`);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${name.replace(/\s+/g, "_").slice(0, 50)}.zip`;
  a.click();
  URL.revokeObjectURL(a.href);
}

/** Configuration for a refinement action (combine or transform). */
interface RefineConfig {
  searchName?: string;
  parameters?: StepParameters;
  operator?: string;
  stepId?: string | number;
  [key: string]: unknown;
}

export async function refineExperiment(
  experimentId: string,
  action: "combine" | "transform",
  config: RefineConfig,
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
