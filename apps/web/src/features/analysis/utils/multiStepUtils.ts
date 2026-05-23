import type { StrategyStepNode, Step } from "@pathfinder/shared";

export function flattenStrategyStepNode(node: StrategyStepNode, recordType: string): Step[] {
  const steps: Step[] = [];
  const id = node.id ?? `step_${Math.random().toString(16).slice(2, 10)}`;
  const params = node.parameters ?? {};

  let primaryInputStepId: string | undefined;
  let secondaryInputStepId: string | undefined;

  if (node.primaryInput) {
    const childSteps = flattenStrategyStepNode(node.primaryInput, recordType);
    steps.push(...childSteps);
    primaryInputStepId = childSteps[childSteps.length - 1]?.id;
  }
  if (node.secondaryInput) {
    const childSteps = flattenStrategyStepNode(node.secondaryInput, recordType);
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
