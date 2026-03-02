import type {
  Experiment,
  ExperimentConfig,
  ExperimentProgressData,
} from "@pathfinder/shared";
import { streamSSEParsed } from "@/lib/sse";

/* ── Config serialization ────────────────────────────────────────── */

function serializeExperimentConfig(
  config: Omit<ExperimentConfig, "name" | "description"> & {
    name?: string;
    description?: string;
  },
): Record<string, unknown> {
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

type PartialConfig = Omit<ExperimentConfig, "name" | "description"> & {
  name?: string;
  description?: string;
};

/* ── Single experiment stream ────────────────────────────────────── */

export type ExperimentSSEHandler = {
  onProgress?: (data: ExperimentProgressData) => void;
  onComplete?: (data: Experiment) => void;
  onError?: (error: string) => void;
};

export function createExperimentStream(
  config: PartialConfig,
  handlers: ExperimentSSEHandler,
  controller?: AbortController,
): AbortController {
  controller ??= new AbortController();

  streamSSEParsed(
    "/api/v1/experiments",
    { body: serializeExperimentConfig(config), signal: controller.signal },
    {
      onError: (err) => handlers.onError?.(err.message),
      onFrame: ({ event, data }) => {
        const d = data as Record<string, unknown>;
        if (event === "experiment_complete") {
          handlers.onComplete?.(d as unknown as Experiment);
        } else if (event === "experiment_error") {
          handlers.onError?.((d.error as string) ?? "Unknown error");
        } else if (event === "experiment_progress" || event === "experiment_end") {
          handlers.onProgress?.(d as unknown as ExperimentProgressData);
        }
      },
    },
  ).catch((err) => console.error("[experiment.stream]", err));

  return controller;
}

/* ── Batch experiment stream ─────────────────────────────────────── */

export interface BatchOrganismTarget {
  organism: string;
  positiveControls: string[];
  negativeControls: string[];
}

export function createBatchExperimentStream(
  base: PartialConfig,
  organismParamName: string,
  targetOrganisms: BatchOrganismTarget[],
  handlers: {
    onProgress?: (data: ExperimentProgressData) => void;
    onComplete?: (experiments: Experiment[], batchId: string) => void;
    onError?: (error: string) => void;
  },
  controller?: AbortController,
): AbortController {
  controller ??= new AbortController();

  streamSSEParsed(
    "/api/v1/experiments/batch",
    {
      body: {
        base: serializeExperimentConfig(base),
        organismParamName,
        targetOrganisms,
      },
      signal: controller.signal,
    },
    {
      onError: (err) => handlers.onError?.(err.message),
      onFrame: ({ event, data }) => {
        const d = data as Record<string, unknown>;
        if (event === "batch_complete") {
          handlers.onComplete?.(
            (d.experiments as Experiment[]) ?? [],
            (d.batchId as string) ?? "",
          );
        } else if (event === "batch_error") {
          handlers.onError?.((d.error as string) ?? "Unknown error");
        } else if (event === "experiment_progress") {
          handlers.onProgress?.(d as unknown as ExperimentProgressData);
        }
      },
    },
  ).catch((err) => console.error("[experiment.stream]", err));

  return controller;
}

/* ── Benchmark stream ────────────────────────────────────────────── */

export interface BenchmarkControlSetInput {
  label: string;
  positiveControls: string[];
  negativeControls: string[];
  controlSetId?: string | null;
  isPrimary: boolean;
}

export function createBenchmarkStream(
  base: PartialConfig,
  controlSets: BenchmarkControlSetInput[],
  handlers: {
    onProgress?: (data: ExperimentProgressData) => void;
    onComplete?: (experiments: Experiment[], benchmarkId: string) => void;
    onError?: (error: string) => void;
  },
  controller?: AbortController,
): AbortController {
  controller ??= new AbortController();

  streamSSEParsed(
    "/api/v1/experiments/benchmark",
    {
      body: { base: serializeExperimentConfig(base), controlSets },
      signal: controller.signal,
    },
    {
      onError: (err) => handlers.onError?.(err.message),
      onFrame: ({ event, data }) => {
        const d = data as Record<string, unknown>;
        if (event === "benchmark_complete") {
          handlers.onComplete?.(
            (d.experiments as Experiment[]) ?? [],
            (d.benchmarkId as string) ?? "",
          );
        } else if (event === "benchmark_error") {
          handlers.onError?.((d.error as string) ?? "Unknown error");
        } else if (event === "experiment_progress") {
          handlers.onProgress?.(d as unknown as ExperimentProgressData);
        }
      },
    },
  ).catch((err) => console.error("[experiment.stream]", err));

  return controller;
}

/* ── AI Assist stream ────────────────────────────────────────────── */

export type WizardStep =
  | "search"
  | "parameters"
  | "controls"
  | "run"
  | "results"
  | "analysis";

export interface AiAssistMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AiAssistHandlers {
  onDelta?: (delta: string) => void;
  onToolCall?: (name: string, status: "start" | "end") => void;
  onComplete?: (fullText: string) => void;
  onError?: (error: string) => void;
}

export function streamAiAssist(
  params: {
    siteId: string;
    step: WizardStep;
    message: string;
    context: Record<string, unknown>;
    history: AiAssistMessage[];
    model?: string;
  },
  handlers: AiAssistHandlers,
): AbortController {
  const controller = new AbortController();
  let fullText = "";
  let completed = false;

  streamSSEParsed(
    "/api/v1/experiments/ai-assist",
    {
      body: {
        siteId: params.siteId,
        step: params.step,
        message: params.message,
        context: params.context,
        history: params.history,
        model: params.model ?? null,
      },
      signal: controller.signal,
    },
    {
      onError: (err) => handlers.onError?.(err.message),
      onFrame: ({ event, data }) => {
        const d = data as Record<string, unknown>;
        if (event === "assistant_delta") {
          const delta = (d.delta as string) ?? "";
          fullText += delta;
          handlers.onDelta?.(delta);
        } else if (event === "assistant_message") {
          const content = (d.content as string) ?? "";
          if (content && content !== fullText) {
            const missing = content.slice(fullText.length);
            if (missing) handlers.onDelta?.(missing);
            fullText = content;
          }
        } else if (event === "tool_call_start") {
          handlers.onToolCall?.((d.name as string) ?? "tool", "start");
        } else if (event === "tool_call_end") {
          handlers.onToolCall?.((d.name as string) ?? "tool", "end");
        } else if (event === "error") {
          handlers.onError?.((d.error as string) ?? "Unknown error");
        } else if (event === "message_end" && !completed) {
          completed = true;
          handlers.onComplete?.(fullText);
        }
      },
    },
  ).catch((err) => console.error("[experiment.stream]", err));

  return controller;
}
