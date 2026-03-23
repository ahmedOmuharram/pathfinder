import type { PlanStepNode, Step } from "@pathfinder/shared";

export function flattenPlanStepNode(node: PlanStepNode, recordType: string): Step[] {
  const steps: Step[] = [];
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
    operator: node.operator ?? null,
    primaryInputStepId: primaryInputStepId ?? null,
    secondaryInputStepId: secondaryInputStepId ?? null,
    isBuilt: false,
    isFiltered: false,
  });

  return steps;
}
