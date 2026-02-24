import type {
  ExperimentConfig,
  EnrichmentAnalysisType,
  OptimizeSpec,
  ParamSpec,
} from "@pathfinder/shared";
import { isMultiPickParam, buildDisplayMap } from "../paramUtils";

export interface BuildConfigInput {
  siteId: string;
  selectedRecordType: string;
  selectedSearch: string;
  parameters: Record<string, string>;
  paramSpecs: ParamSpec[];
  positiveControls: string[];
  negativeControls: string[];
  enableCV: boolean;
  kFolds: number;
  enrichments: Set<EnrichmentAnalysisType>;
  name: string;
  controlsSearchName: string;
  controlsParamName: string;
  optimizeSpecs?: Map<string, OptimizeSpec>;
  optimizationBudget?: number;
  optimizationObjective?: string;
}

export function buildExperimentConfig(input: BuildConfigInput): ExperimentConfig {
  const {
    siteId,
    selectedRecordType,
    selectedSearch,
    parameters,
    paramSpecs,
    positiveControls,
    negativeControls,
    enableCV,
    kFolds,
    enrichments,
    name,
    controlsSearchName,
    controlsParamName,
  } = input;

  const fixedParams: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(parameters)) {
    if (v === "") continue;
    const spec = paramSpecs.find((s) => s.name === k);
    if (spec && isMultiPickParam(spec)) {
      fixedParams[k] = v.split(",").filter(Boolean);
    } else {
      fixedParams[k] = v;
    }
  }

  const config: ExperimentConfig = {
    siteId,
    recordType: selectedRecordType,
    searchName: selectedSearch,
    parameters: fixedParams,
    positiveControls,
    negativeControls,
    controlsSearchName,
    controlsParamName,
    controlsValueFormat: "newline",
    enableCrossValidation: enableCV,
    kFolds,
    enrichmentTypes: Array.from(enrichments) as EnrichmentAnalysisType[],
    name: name || `${selectedSearch} experiment`,
    parameterDisplayValues: buildDisplayMap(parameters, paramSpecs),
  };

  const { optimizeSpecs, optimizationBudget, optimizationObjective } = input;
  if (optimizeSpecs && optimizeSpecs.size > 0) {
    config.optimizationSpecs = Array.from(optimizeSpecs.values());
    config.optimizationBudget = optimizationBudget ?? 30;
    config.optimizationObjective = optimizationObjective ?? "balanced_accuracy";
  }

  return config;
}
