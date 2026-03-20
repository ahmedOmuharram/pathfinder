import type { CombineOperator, PlanStepNode, StrategyPlan } from "@pathfinder/shared";
import { DEFAULT_STREAM_NAME } from "@pathfinder/shared";
import type { Step, Strategy } from "@pathfinder/shared";
import type { StepParameters } from "./types";

export type SerializedStrategyPlan = {
  plan: StrategyPlan;
  name: string;
  recordType: string | null;
};

function sanitizeParametersForPlan(params: StepParameters): StepParameters {
  // UI-only sentinel must never be persisted/sent.
  const next: StepParameters = {};
  for (const [key, value] of Object.entries(params)) {
    if (value === "@@fake@@") continue;
    if (Array.isArray(value) && value.includes("@@fake@@")) continue;
    next[key] = value;
  }
  return next;
}

export function serializeStrategyPlan(
  stepsById: Record<string, Step>,
  strategy: Strategy | null,
): SerializedStrategyPlan | null {
  const steps = Object.values(stepsById);
  if (steps.length === 0) return null;

  const recordType = strategy?.recordType ?? steps[0]?.recordType ?? "gene";

  const inputStepIds = new Set<string>();
  for (const step of steps) {
    if (step.primaryInputStepId != null) inputStepIds.add(step.primaryInputStepId);
    if (step.secondaryInputStepId != null) inputStepIds.add(step.secondaryInputStepId);
  }
  const rootSteps = steps.filter((s) => !inputStepIds.has(s.id));
  // Single-output invariant: do not serialize a plan if the graph has multiple outputs.
  // This prevents silently "picking" an arbitrary root and saving a broken strategy.
  if (rootSteps.length !== 1) return null;
  const rootStep = rootSteps[0]!;

  const buildNode = (stepId: string): PlanStepNode | null => {
    const step = stepsById[stepId];
    if (!step) return null;

    const isCombine =
      step.primaryInputStepId != null && step.secondaryInputStepId != null;
    // Combine nodes don't have a user-selected searchName in the UI; use the backend's
    // placeholder. Combine steps are structural (primary+secondary+operator) and do not
    // require a real WDK question name.
    const resolvedSearchName =
      step.searchName != null && step.searchName !== ""
        ? step.searchName
        : isCombine
          ? "__combine__"
          : null;
    if (resolvedSearchName == null) return null;

    const node: PlanStepNode = {
      id: step.id,
      searchName: resolvedSearchName,
      displayName: step.displayName,
      parameters: sanitizeParametersForPlan(step.parameters ?? {}),
    };

    if (step.primaryInputStepId != null) {
      const primary = buildNode(step.primaryInputStepId);
      if (!primary) return null;
      node.primaryInput = primary;
    }

    if (step.secondaryInputStepId != null) {
      // secondary implies primary for our plan contract
      if (step.primaryInputStepId == null) return null;
      const secondary = buildNode(step.secondaryInputStepId);
      if (!secondary) return null;
      node.secondaryInput = secondary;
      if (step.operator == null) return null;
      node.operator = step.operator as CombineOperator;
      if (step.operator === "COLOCATE" && step.colocationParams) {
        node.colocationParams = step.colocationParams;
      }
    }

    return node;
  };

  const rootNode = buildNode(rootStep.id);
  if (!rootNode) return null;

  const name =
    strategy?.name != null && strategy.name !== ""
      ? strategy.name
      : DEFAULT_STREAM_NAME;
  const metadata: { name: string; description?: string } = { name };
  if (strategy?.description != null) {
    metadata.description = strategy.description;
  }
  return {
    name,
    recordType,
    plan: {
      recordType,
      root: rootNode,
      metadata,
    },
  };
}
