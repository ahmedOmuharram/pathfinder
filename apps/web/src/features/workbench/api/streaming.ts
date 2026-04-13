/**
 * Typed SSE streaming helpers for experiment execution.
 *
 * Replaces the old `operationSubscribe` + Redis-Streams flow. Each endpoint
 * now POSTs a JSON body and streams typed progress events directly back over
 * SSE (one long-running request), consumed via `streamTypedEvents`.
 */

import type {
  Experiment,
  ExperimentConfig,
  ExperimentProgressData,
} from "@pathfinder/shared";
import { streamTypedEvents } from "@/lib/sse/typedEventStream";
import type { StepParameters } from "@/lib/strategyGraph/types";

// ── Config serialization (unchanged from the old client) ───────────────────

type SerializedExperimentConfig = {
  siteId: string;
  recordType?: string | undefined;
  mode: string;
  searchName?: string | undefined;
  parameters?: StepParameters | undefined;
  positiveControls?: string[] | undefined;
  negativeControls?: string[] | undefined;
  controlsSearchName?: string | undefined;
  controlsParamName?: string | undefined;
  controlsValueFormat?: "pipe" | "comma" | "newline" | undefined;
  enableCrossValidation?: boolean | undefined;
  kFolds?: number | undefined;
  enrichmentTypes?: string[] | undefined;
  name?: string | undefined;
  description?: string | undefined;
};

export interface BatchOrganismTarget {
  organism: string;
  positiveControls?: string[];
  negativeControls?: string[];
}

export interface BenchmarkControlSetInput {
  label: string;
  positiveControls: string[];
  negativeControls: string[];
  controlSetId?: string | null;
  isPrimary: boolean;
}

// ── Event shapes emitted by the backend (camelCase wire format) ────────────

interface ExperimentProgressEvent {
  type: "experiment_progress";
  data: ExperimentProgressData | Record<string, unknown>;
}

interface ExperimentCompleteEvent {
  type: "experiment_complete";
  experiment: Experiment;
}

interface ExperimentErrorEvent {
  type: "experiment_error";
  error: string;
}

interface ExperimentEndEvent {
  type: "experiment_end";
}

export type ExperimentStreamEvent =
  | ExperimentProgressEvent
  | ExperimentCompleteEvent
  | ExperimentErrorEvent
  | ExperimentEndEvent;

interface BatchCompleteEvent {
  type: "batch_complete";
  batchId: string;
  experiments: Experiment[];
}

interface BatchErrorEvent {
  type: "batch_error";
  error: string;
}

export type BatchStreamEvent =
  | ExperimentProgressEvent
  | BatchCompleteEvent
  | BatchErrorEvent;

interface BenchmarkCompleteEvent {
  type: "benchmark_complete";
  benchmarkId: string;
  experiments: Experiment[];
}

interface BenchmarkErrorEvent {
  type: "benchmark_error";
  error: string;
}

export type BenchmarkStreamEvent =
  | ExperimentProgressEvent
  | BenchmarkCompleteEvent
  | BenchmarkErrorEvent;

// ── Public generators ──────────────────────────────────────────────────────

type RunOptions = {
  signal?: AbortSignal;
};

function serializeConfig(config: ExperimentConfig): SerializedExperimentConfig {
  return {
    siteId: config.siteId,
    recordType: config.recordType,
    mode: (config as SerializedExperimentConfig).mode ?? "single",
    searchName: config.searchName,
    parameters: config.parameters as StepParameters | undefined,
    positiveControls: config.positiveControls,
    negativeControls: config.negativeControls,
    controlsSearchName: config.controlsSearchName,
    controlsParamName: config.controlsParamName,
    controlsValueFormat: (config as SerializedExperimentConfig).controlsValueFormat,
    enableCrossValidation: config.enableCrossValidation,
    kFolds: config.kFolds,
    enrichmentTypes: config.enrichmentTypes,
    name: config.name,
    description: config.description,
  };
}

function buildRunOptions(
  method: "POST",
  body: unknown,
  signal: AbortSignal | undefined,
) {
  return {
    method,
    body,
    ...(signal !== undefined ? { signal } : {}),
  } as const;
}

export async function* createExperimentStream(
  config: ExperimentConfig,
  options: RunOptions = {},
): AsyncGenerator<ExperimentStreamEvent> {
  yield* streamTypedEvents<ExperimentStreamEvent>(
    "/api/v1/experiments/",
    buildRunOptions("POST", serializeConfig(config), options.signal),
  );
}

export async function* createBatchExperimentStream(
  baseConfig: ExperimentConfig,
  organismParamName: string,
  targets: BatchOrganismTarget[],
  options: RunOptions = {},
): AsyncGenerator<BatchStreamEvent> {
  yield* streamTypedEvents<BatchStreamEvent>(
    "/api/v1/experiments/batch",
    buildRunOptions(
      "POST",
      {
        base: serializeConfig(baseConfig),
        organismParamName,
        targetOrganisms: targets,
      },
      options.signal,
    ),
  );
}

export async function* createBenchmarkStream(
  baseConfig: ExperimentConfig,
  controlSets: BenchmarkControlSetInput[],
  options: RunOptions = {},
): AsyncGenerator<BenchmarkStreamEvent> {
  yield* streamTypedEvents<BenchmarkStreamEvent>(
    "/api/v1/experiments/benchmark",
    buildRunOptions(
      "POST",
      {
        base: serializeConfig(baseConfig),
        controlSets,
      },
      options.signal,
    ),
  );
}
