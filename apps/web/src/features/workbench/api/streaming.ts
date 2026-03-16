import type {
  Experiment,
  ExperimentConfig,
  ExperimentProgressData,
} from "@pathfinder/shared";
import { requestJson } from "@/lib/api/http";
import {
  subscribeToOperation,
  type OperationSubscription,
} from "@/lib/operationSubscribe";
import type { StepParameters } from "@/lib/strategyGraph/types";

/* ── Config serialization ────────────────────────────────────────── */

/** Serialized experiment config payload sent to the API. */
type SerializedExperimentConfig = {
  siteId: string;
  recordType?: string;
  mode: string;
  searchName?: string;
  parameters?: StepParameters;
  positiveControls?: string[];
  negativeControls?: string[];
  controlsSearchName?: string;
  controlsParamName?: string;
  controlsValueFormat: string;
  enableCrossValidation?: boolean;
  kFolds?: number;
  enrichmentTypes?: string[];
  name: string;
  description: string;
  [key: string]: unknown;
};

function serializeExperimentConfig(config: PartialConfig): SerializedExperimentConfig {
  return {
    siteId: config.siteId,
    recordType: config.recordType,
    mode: config.mode ?? "single",
    searchName: config.searchName,
    parameters: config.parameters,
    positiveControls: config.positiveControls,
    negativeControls: config.negativeControls,
    controlsSearchName: config.controlsSearchName,
    controlsParamName: config.controlsParamName,
    controlsValueFormat: config.controlsValueFormat ?? "newline",
    enableCrossValidation: config.enableCrossValidation,
    kFolds: config.kFolds,
    enrichmentTypes: config.enrichmentTypes,
    name: config.name ?? "Untitled Experiment",
    description: config.description ?? "",
    ...(config.stepTree ? { stepTree: config.stepTree } : {}),
    ...(config.sourceStrategyId ? { sourceStrategyId: config.sourceStrategyId } : {}),
    ...(config.optimizationTargetStep
      ? { optimizationTargetStep: config.optimizationTargetStep }
      : {}),
    ...(config.optimizationSpecs && config.optimizationSpecs.length > 0
      ? {
          optimizationSpecs: config.optimizationSpecs,
          optimizationBudget: config.optimizationBudget ?? 30,
          optimizationObjective: config.optimizationObjective ?? "balanced_accuracy",
        }
      : {}),
    ...(config.parameterDisplayValues
      ? { parameterDisplayValues: config.parameterDisplayValues }
      : {}),
    ...(config.parentExperimentId
      ? { parentExperimentId: config.parentExperimentId }
      : {}),
    ...(config.targetGeneIds && config.targetGeneIds.length > 0
      ? { targetGeneIds: config.targetGeneIds }
      : {}),
    ...(config.enableStepAnalysis
      ? {
          enableStepAnalysis: true,
          ...(config.stepAnalysisPhases
            ? { stepAnalysisPhases: config.stepAnalysisPhases }
            : {}),
        }
      : {}),
    ...(config.sortAttribute
      ? {
          sortAttribute: config.sortAttribute,
          sortDirection: config.sortDirection ?? "ASC",
        }
      : {}),
    ...(config.controlSetId ? { controlSetId: config.controlSetId } : {}),
    ...(config.thresholdKnobs && config.thresholdKnobs.length > 0
      ? {
          thresholdKnobs: config.thresholdKnobs,
          treeOptimizationObjective:
            config.treeOptimizationObjective ?? "precision_at_50",
          treeOptimizationBudget: config.treeOptimizationBudget ?? 50,
        }
      : {}),
    ...(config.operatorKnobs && config.operatorKnobs.length > 0
      ? {
          operatorKnobs: config.operatorKnobs,
          ...(!config.thresholdKnobs?.length
            ? {
                treeOptimizationObjective:
                  config.treeOptimizationObjective ?? "precision_at_50",
                treeOptimizationBudget: config.treeOptimizationBudget ?? 50,
              }
            : {}),
        }
      : {}),
    ...(config.maxListSize != null ? { maxListSize: config.maxListSize } : {}),
  };
}

/** Fields that have backend defaults and needn't be supplied by callers. */
type DefaultedConfigKeys =
  | "name"
  | "description"
  | "mode"
  | "optimizationBudget"
  | "optimizationObjective"
  | "enableStepAnalysis"
  | "treeOptimizationObjective"
  | "treeOptimizationBudget"
  | "sortDirection"
  | "controlsValueFormat";

type PartialConfig = Omit<ExperimentConfig, DefaultedConfigKeys> &
  Partial<Pick<ExperimentConfig, DefaultedConfigKeys>>;

/* ── SSE event data shapes for experiment streams ────────────────── */

/** Data payload for experiment_complete events. */
interface ExperimentCompleteData extends Experiment {}

/** Data payload for experiment_error / batch_error / benchmark_error. */
interface ExperimentErrorData {
  error: string;
}

/** Data payload for batch_complete events. */
interface BatchCompleteData {
  experiments: Experiment[];
  batchId: string;
}

/** Data payload for benchmark_complete events. */
interface BenchmarkCompleteData {
  experiments: Experiment[];
  benchmarkId: string;
}

/* ── Type guards for SSE data payloads ───────────────────────────── */

function isExperimentErrorData(data: unknown): data is ExperimentErrorData {
  return (
    typeof data === "object" &&
    data !== null &&
    "error" in data &&
    typeof (data as ExperimentErrorData).error === "string"
  );
}

function isBatchCompleteData(data: unknown): data is BatchCompleteData {
  return (
    typeof data === "object" &&
    data !== null &&
    "experiments" in data &&
    "batchId" in data
  );
}

function isBenchmarkCompleteData(data: unknown): data is BenchmarkCompleteData {
  return (
    typeof data === "object" &&
    data !== null &&
    "experiments" in data &&
    "benchmarkId" in data
  );
}

/* ── Single experiment stream ────────────────────────────────────── */

export type ExperimentSSEHandler = {
  onProgress?: (data: ExperimentProgressData) => void;
  onComplete?: (data: Experiment) => void;
  onError?: (error: string) => void;
};

export async function createExperimentStream(
  config: PartialConfig,
  handlers: ExperimentSSEHandler,
): Promise<OperationSubscription> {
  const resp = await requestJson<{ operationId: string }>("/api/v1/experiments", {
    method: "POST",
    body: serializeExperimentConfig(config),
  });

  return subscribeToOperation<
    ExperimentCompleteData | ExperimentErrorData | ExperimentProgressData
  >(resp.operationId, {
    onEvent: ({ type, data }) => {
      if (typeof data !== "object" || data === null) return;
      if (type === "experiment_complete") {
        handlers.onComplete?.(data as ExperimentCompleteData);
      } else if (type === "experiment_error" && isExperimentErrorData(data)) {
        handlers.onError?.(data.error);
      } else if (type === "experiment_progress" || type === "experiment_end") {
        handlers.onProgress?.(data as ExperimentProgressData);
      }
    },
    onError: (err) => handlers.onError?.(err.message),
    endEventTypes: new Set(["experiment_end"]),
  });
}

/* ── Batch experiment stream ─────────────────────────────────────── */

export interface BatchOrganismTarget {
  organism: string;
  positiveControls?: string[] | null;
  negativeControls?: string[] | null;
}

export async function createBatchExperimentStream(
  base: PartialConfig,
  organismParamName: string,
  targetOrganisms: BatchOrganismTarget[],
  handlers: {
    onProgress?: (data: ExperimentProgressData) => void;
    onComplete?: (experiments: Experiment[], batchId: string) => void;
    onError?: (error: string) => void;
  },
): Promise<OperationSubscription> {
  const resp = await requestJson<{ operationId: string }>("/api/v1/experiments/batch", {
    method: "POST",
    body: {
      base: serializeExperimentConfig(base),
      organismParamName,
      targetOrganisms,
    },
  });

  return subscribeToOperation<
    BatchCompleteData | ExperimentErrorData | ExperimentProgressData
  >(resp.operationId, {
    onEvent: ({ type, data }) => {
      if (typeof data !== "object" || data === null) return;
      if (type === "batch_complete" && isBatchCompleteData(data)) {
        handlers.onComplete?.(data.experiments, data.batchId);
      } else if (type === "batch_error" && isExperimentErrorData(data)) {
        handlers.onError?.(data.error);
      } else if (type === "experiment_progress") {
        handlers.onProgress?.(data as ExperimentProgressData);
      }
    },
    onError: (err) => handlers.onError?.(err.message),
    endEventTypes: new Set(["batch_complete", "batch_error"]),
  });
}

/* ── Benchmark stream ────────────────────────────────────────────── */

export interface BenchmarkControlSetInput {
  label: string;
  positiveControls: string[];
  negativeControls: string[];
  controlSetId?: string | null;
  isPrimary: boolean;
}

export async function createBenchmarkStream(
  base: PartialConfig,
  controlSets: BenchmarkControlSetInput[],
  handlers: {
    onProgress?: (data: ExperimentProgressData) => void;
    onComplete?: (experiments: Experiment[], benchmarkId: string) => void;
    onError?: (error: string) => void;
  },
): Promise<OperationSubscription> {
  const resp = await requestJson<{ operationId: string }>(
    "/api/v1/experiments/benchmark",
    {
      method: "POST",
      body: { base: serializeExperimentConfig(base), controlSets },
    },
  );

  return subscribeToOperation<
    BenchmarkCompleteData | ExperimentErrorData | ExperimentProgressData
  >(resp.operationId, {
    onEvent: ({ type, data }) => {
      if (typeof data !== "object" || data === null) return;
      if (type === "benchmark_complete" && isBenchmarkCompleteData(data)) {
        handlers.onComplete?.(data.experiments, data.benchmarkId);
      } else if (type === "benchmark_error" && isExperimentErrorData(data)) {
        handlers.onError?.(data.error);
      } else if (type === "experiment_progress") {
        handlers.onProgress?.(data as ExperimentProgressData);
      }
    },
    onError: (err) => handlers.onError?.(err.message),
    endEventTypes: new Set(["benchmark_complete", "benchmark_error"]),
  });
}
