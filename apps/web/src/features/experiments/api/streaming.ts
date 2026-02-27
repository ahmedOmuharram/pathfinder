import type {
  Experiment,
  ExperimentConfig,
  ExperimentProgressData,
} from "@pathfinder/shared";
import { buildUrl, getAuthHeaders } from "@/lib/api/http";

export type ExperimentSSEHandler = {
  onProgress?: (data: ExperimentProgressData) => void;
  onComplete?: (data: Experiment) => void;
  onError?: (error: string) => void;
};

export function createExperimentStream(
  config: Omit<ExperimentConfig, "name" | "description"> & {
    name?: string;
    description?: string;
  },
  handlers: ExperimentSSEHandler,
): AbortController {
  const controller = new AbortController();
  const url = buildUrl("/api/v1/experiments");

  (async () => {
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: {
          ...getAuthHeaders(undefined, {
            accept: "text/event-stream",
            contentType: "application/json",
          }),
        },
        body: JSON.stringify({
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
          ...(config.sourceStrategyId
            ? { sourceStrategyId: config.sourceStrategyId }
            : {}),
          ...(config.optimizationTargetStep
            ? { optimizationTargetStep: config.optimizationTargetStep }
            : {}),
          ...(config.optimizationSpecs && config.optimizationSpecs.length > 0
            ? {
                optimizationSpecs: config.optimizationSpecs,
                optimizationBudget: config.optimizationBudget ?? 30,
                optimizationObjective: config.optimizationObjective ?? "balanced",
              }
            : {}),
          ...(config.parameterDisplayValues
            ? { parameterDisplayValues: config.parameterDisplayValues }
            : {}),
          ...(config.parentExperimentId
            ? { parentExperimentId: config.parentExperimentId }
            : {}),
          ...(config.enableTreeOptimization
            ? {
                enableTreeOptimization: true,
                treeOptimizationBudget: config.treeOptimizationBudget ?? 20,
                optimizeOperators: config.optimizeOperators ?? true,
                optimizeOrthologs: config.optimizeOrthologs ?? false,
                optimizeStructure: config.optimizeStructure ?? false,
                ...(config.orthologOrganisms
                  ? { orthologOrganisms: config.orthologOrganisms }
                  : {}),
                optimizationObjective:
                  config.optimizationObjective ?? "balanced_accuracy",
              }
            : {}),
        }),
        signal: controller.signal,
        credentials: "include",
      });

      if (!resp.ok || !resp.body) {
        handlers.onError?.(`HTTP ${resp.status}: ${resp.statusText}`);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let eventType = "";
      let dataStr = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            dataStr = line.slice(6);
          } else if (line === "" && dataStr) {
            try {
              const parsed = JSON.parse(dataStr);
              if (eventType === "experiment_complete") {
                handlers.onComplete?.(parsed as Experiment);
              } else if (eventType === "experiment_error") {
                handlers.onError?.(parsed.error ?? "Unknown error");
              } else if (
                eventType === "experiment_progress" ||
                eventType === "experiment_end"
              ) {
                handlers.onProgress?.(parsed as ExperimentProgressData);
              }
            } catch {
              /* ignore parse errors */
            }
            eventType = "";
            dataStr = "";
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        handlers.onError?.(String(err));
      }
    }
  })();

  return controller;
}

export interface BatchOrganismTarget {
  organism: string;
  positiveControls: string[];
  negativeControls: string[];
}

export function createBatchExperimentStream(
  base: Omit<ExperimentConfig, "name" | "description"> & {
    name?: string;
    description?: string;
  },
  organismParamName: string,
  targetOrganisms: BatchOrganismTarget[],
  handlers: {
    onProgress?: (data: ExperimentProgressData) => void;
    onComplete?: (experiments: Experiment[], batchId: string) => void;
    onError?: (error: string) => void;
  },
): AbortController {
  const controller = new AbortController();
  const url = buildUrl("/api/v1/experiments/batch");

  (async () => {
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: {
          ...getAuthHeaders(undefined, {
            accept: "text/event-stream",
            contentType: "application/json",
          }),
        },
        body: JSON.stringify({ base, organismParamName, targetOrganisms }),
        signal: controller.signal,
        credentials: "include",
      });

      if (!resp.ok || !resp.body) {
        handlers.onError?.(`HTTP ${resp.status}: ${resp.statusText}`);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let eventType = "";
      let dataStr = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (line.startsWith("event: ")) eventType = line.slice(7).trim();
          else if (line.startsWith("data: ")) dataStr = line.slice(6);
          else if (line === "" && dataStr) {
            try {
              const parsed = JSON.parse(dataStr);
              if (eventType === "batch_complete") {
                handlers.onComplete?.(parsed.experiments ?? [], parsed.batchId ?? "");
              } else if (eventType === "batch_error") {
                handlers.onError?.(parsed.error ?? "Unknown error");
              } else if (eventType === "experiment_progress") {
                handlers.onProgress?.(parsed as ExperimentProgressData);
              }
            } catch {
              /* ignore parse errors */
            }
            eventType = "";
            dataStr = "";
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") handlers.onError?.(String(err));
    }
  })();

  return controller;
}

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
  const url = buildUrl("/api/v1/experiments/ai-assist");

  (async () => {
    let fullText = "";
    let completed = false;
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: {
          ...getAuthHeaders(undefined, {
            accept: "text/event-stream",
            contentType: "application/json",
          }),
        },
        body: JSON.stringify({
          siteId: params.siteId,
          step: params.step,
          message: params.message,
          context: params.context,
          history: params.history,
          model: params.model ?? null,
        }),
        signal: controller.signal,
        credentials: "include",
      });

      if (!resp.ok || !resp.body) {
        handlers.onError?.(`HTTP ${resp.status}: ${resp.statusText}`);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let eventType = "";
      let dataStr = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            dataStr = line.slice(6);
          } else if (line === "" && dataStr) {
            try {
              const parsed = JSON.parse(dataStr);
              if (eventType === "assistant_delta") {
                const delta = parsed.delta ?? "";
                fullText += delta;
                handlers.onDelta?.(delta);
              } else if (eventType === "assistant_message") {
                const content = parsed.content ?? "";
                if (content && content !== fullText) {
                  const missing = content.slice(fullText.length);
                  if (missing) handlers.onDelta?.(missing);
                  fullText = content;
                }
              } else if (eventType === "tool_call_start") {
                handlers.onToolCall?.(parsed.name ?? "tool", "start");
              } else if (eventType === "tool_call_end") {
                handlers.onToolCall?.(parsed.name ?? "tool", "end");
              } else if (eventType === "error") {
                handlers.onError?.(parsed.error ?? "Unknown error");
              } else if (eventType === "message_end" && !completed) {
                completed = true;
                handlers.onComplete?.(fullText);
              }
            } catch {
              /* ignore parse errors */
            }
            eventType = "";
            dataStr = "";
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        handlers.onError?.(String(err));
      }
    }
  })();

  return controller;
}
