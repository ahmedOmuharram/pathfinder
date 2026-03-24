import type { Experiment } from "@pathfinder/shared";
import { requestBlob, requestJson, requestVoid } from "@/lib/api/http";
import { ExperimentSchema } from "@/lib/api/schemas/experiment";
import { RefineResponseSchema } from "@/lib/api/schemas/analysis";
import type { StepParameters } from "@/lib/strategyGraph/types";

export async function getExperiment(experimentId: string): Promise<Experiment> {
  const raw = await requestJson(ExperimentSchema, `/api/v1/experiments/${experimentId}`);
  return raw as unknown as Experiment;
}

export async function deleteExperiment(experimentId: string): Promise<void> {
  await requestVoid(`/api/v1/experiments/${experimentId}`, { method: "DELETE" });
}

export async function updateExperimentNotes(
  experimentId: string,
  notes: string,
): Promise<Experiment> {
  const raw = await requestJson(
    ExperimentSchema,
    `/api/v1/experiments/${experimentId}`,
    { method: "PATCH", body: { notes } },
  );
  return raw as unknown as Experiment;
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
  const raw = await requestJson(
    RefineResponseSchema,
    `/api/v1/experiments/${experimentId}/refine`,
    { method: "POST", body: { action, ...config } },
  );
  return { success: raw.success, ...(raw.newStepId != null ? { newStepId: raw.newStepId } : {}) };
}

export async function reEvaluateExperiment(experimentId: string): Promise<Experiment> {
  const raw = await requestJson(
    ExperimentSchema,
    `/api/v1/experiments/${experimentId}/re-evaluate`,
    { method: "POST" },
  );
  return raw as unknown as Experiment;
}
