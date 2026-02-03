import type { PlanNode, StrategyPlan } from "@pathfinder/shared";
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

  const buildNode = (stepId: string): PlanNode | null => {
    const step = stepsById[stepId];
    if (!step) return null;

    if (step.type === "search") {
      if (!step.searchName) return null;
      return {
        type: "search",
        id: step.id,
        searchName: step.searchName,
        displayName: step.displayName,
        parameters: sanitizeParametersForPlan(step.parameters || {}),
      };
    }

    if (step.type === "combine") {
      if (!step.primaryInputStepId || !step.secondaryInputStepId) return null;
      if (!step.operator) return null;
      const left = buildNode(step.primaryInputStepId);
      const right = buildNode(step.secondaryInputStepId);
      if (!left || !right) return null;
      return {
        type: "combine",
        id: step.id,
        displayName: step.displayName,
        operator: step.operator,
        left,
        right,
      };
    }

    if (step.type === "transform") {
      if (!step.primaryInputStepId) return null;
      const transformName = step.transformName ?? step.searchName;
      if (!transformName) return null;
      const input = buildNode(step.primaryInputStepId);
      if (!input) return null;
      return {
        type: "transform",
        id: step.id,
        displayName: step.displayName,
        transformName,
        parameters: sanitizeParametersForPlan(step.parameters || {}),
        input,
      };
    }

    return null;
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
