import type {
  EnrichmentAnalysisType,
  ExperimentConfig,
  PlanStepNode,
  StepAnalysisPhase,
  CombineOperator,
  StrategyStep,
  StrategyWithMeta,
  ResolvedGene,
} from "@pathfinder/shared";
import type { StepAnalysisConfig } from "./ConfigPanel";
import { getRootStepId } from "@/lib/strategyGraph";

export function generateStepId(): string {
  return `step_${Math.random().toString(16).slice(2, 10)}`;
}

export function buildLocalStrategy(
  stepsById: Record<string, StrategyStep>,
  siteId: string,
  recordType: string,
): StrategyWithMeta | null {
  const steps = Object.values(stepsById);
  if (steps.length === 0) return null;
  const rootStepId = getRootStepId(steps);
  return {
    id: "experiment-draft",
    name: "Experiment Strategy",
    siteId,
    recordType,
    steps,
    rootStepId,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

export const DEFAULT_STEP_ANALYSIS: StepAnalysisConfig = {
  enabled: false,
  phases: new Set<StepAnalysisPhase>([
    "step_evaluation",
    "operator_comparison",
    "contribution",
    "sensitivity",
  ]),
};

export function flattenPlanStepNode(
  node: PlanStepNode,
  recordType: string,
): StrategyStep[] {
  const steps: StrategyStep[] = [];
  const id = node.id ?? `step_${Math.random().toString(16).slice(2, 10)}`;
  const params: Record<string, string> = {};
  if (node.parameters) {
    for (const [k, v] of Object.entries(node.parameters)) {
      params[k] = String(v ?? "");
    }
  }

  let primaryInputStepId: string | undefined;
  let secondaryInputStepId: string | undefined;

  if (node.primaryInput) {
    const childSteps = flattenPlanStepNode(node.primaryInput, recordType);
    steps.push(...childSteps);
    primaryInputStepId = childSteps[childSteps.length - 1]?.id;
  }
  if (node.secondaryInput) {
    const childSteps = flattenPlanStepNode(node.secondaryInput, recordType);
    steps.push(...childSteps);
    secondaryInputStepId = childSteps[childSteps.length - 1]?.id;
  }

  steps.push({
    id,
    displayName: node.displayName ?? node.searchName,
    searchName: node.searchName,
    recordType,
    parameters: params,
    operator: node.operator as CombineOperator | undefined,
    primaryInputStepId,
    secondaryInputStepId,
  });

  return steps;
}

export function applyMultiStepClone(
  config: ExperimentConfig,
  setters: {
    setName: (v: string) => void;
    setSelectedRecordType: (v: string) => void;
    setPositiveGenes: (v: ResolvedGene[]) => void;
    setNegativeGenes: (v: ResolvedGene[]) => void;
    setEnableCV: (v: boolean) => void;
    setKFolds: (v: number) => void;
    setKFoldsDraft: (v: string) => void;
    setEnrichments: (v: Set<EnrichmentAnalysisType>) => void;
    loadImportedSteps: (steps: StrategyStep[], rt?: string) => void;
    setStepAnalysis: (v: StepAnalysisConfig) => void;
  },
  enableOptimize: boolean,
) {
  setters.setName(`${config.name} (clone)`);
  setters.setSelectedRecordType(config.recordType);
  setters.setEnableCV(config.enableCrossValidation);
  setters.setKFolds(config.kFolds);
  setters.setKFoldsDraft(String(config.kFolds));
  setters.setEnrichments(new Set(config.enrichmentTypes));

  const toResolved = (ids: string[]): ResolvedGene[] =>
    ids.map((id) => ({
      geneId: id,
      displayName: id,
      organism: "",
      product: "",
      geneName: "",
      geneType: "",
      location: "",
    }));
  setters.setPositiveGenes(toResolved(config.positiveControls));
  setters.setNegativeGenes(toResolved(config.negativeControls));

  if (config.stepTree) {
    const steps = flattenPlanStepNode(config.stepTree, config.recordType);
    setters.loadImportedSteps(steps, config.recordType);
  }

  const shouldEnableAnalysis = enableOptimize || config.enableStepAnalysis === true;
  setters.setStepAnalysis({
    enabled: shouldEnableAnalysis,
    phases: new Set<StepAnalysisPhase>(
      config.stepAnalysisPhases ?? [
        "step_evaluation",
        "operator_comparison",
        "contribution",
        "sensitivity",
      ],
    ),
  });
}
