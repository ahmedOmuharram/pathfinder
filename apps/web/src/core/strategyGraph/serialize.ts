import type { PlanStepNode, StrategyPlan } from "@pathfinder/shared";
import type { Step, Strategy } from "./types";

export type SerializedStrategyPlan = {
  plan: StrategyPlan;
  name: string;
  recordType: string | null;
};

function sanitizeParametersForPlan(
  params: Record<string, unknown>
): Record<string, unknown> {
  // UI-only sentinel must never be persisted/sent.
  const next: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(params || {})) {
    if (value === "@@fake@@") continue;
    if (Array.isArray(value) && value.includes("@@fake@@")) continue;
    next[key] = value;
  }
  return next;
}

export function serializeStrategyPlan(
  stepsById: Record<string, Step>,
  strategy: Strategy | null
): SerializedStrategyPlan | null {
  const steps = Object.values(stepsById);
  if (steps.length === 0) return null;

  const inputStepIds = new Set<string>();
  for (const step of steps) {
    if (step.primaryInputStepId) inputStepIds.add(step.primaryInputStepId);
    if (step.secondaryInputStepId) inputStepIds.add(step.secondaryInputStepId);
  }
  const rootSteps = steps.filter((s) => !inputStepIds.has(s.id));
  // Single-output invariant: do not serialize a plan if the graph has multiple outputs.
  // This prevents silently "picking" an arbitrary root and saving a broken strategy.
  if (rootSteps.length !== 1) return null;
  const rootStep = rootSteps[0];

  const buildNode = (stepId: string): PlanStepNode | null => {
    const step = stepsById[stepId];
    if (!step) return null;

    if (!step.searchName) return null;

    const node: PlanStepNode = {
      id: step.id,
      searchName: step.searchName,
      displayName: step.displayName,
      parameters: sanitizeParametersForPlan(step.parameters || {}),
    };

    if (step.primaryInputStepId) {
      const primary = buildNode(step.primaryInputStepId);
      if (!primary) return null;
      node.primaryInput = primary;
    }

    if (step.secondaryInputStepId) {
      // secondary implies primary for our plan contract
      if (!step.primaryInputStepId) return null;
      const secondary = buildNode(step.secondaryInputStepId);
      if (!secondary) return null;
      node.secondaryInput = secondary;
      if (!step.operator) return null;
      node.operator = step.operator;
      if (step.operator === "COLOCATE" && step.colocationParams) {
        node.colocationParams = step.colocationParams;
      }
    }

    return node;
  };

  const rootNode = buildNode(rootStep.id);
  if (!rootNode) return null;

  const name = strategy?.name || "Draft Strategy";
  const recordType = strategy?.recordType || steps[0]?.recordType || "gene";
  return {
    name,
    recordType,
    plan: {
      recordType,
      root: rootNode,
      metadata: {
        name,
        description: strategy?.description ?? undefined,
      },
    },
  };
}
