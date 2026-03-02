import type { Step, StrategyWithMeta } from "@pathfinder/shared";
import type { StrategyNode, StrategyResponse } from "../api/crud";

/**
 * Convert the nested {@link StrategyResponse} returned by the experiment
 * strategy endpoint into the flat {@link StrategyWithMeta} format expected
 * by the ReactFlow-based strategy graph.
 */
export function strategyResponseToStrategy(
  resp: StrategyResponse,
  siteId: string,
  recordType?: string,
): StrategyWithMeta {
  const steps: Step[] = [];
  flattenTree(resp.stepTree, resp.steps, steps);

  const rootId = String(resp.stepTree.stepId);

  return {
    id: `exp-strategy-${resp.strategyId}`,
    name: resp.name,
    siteId,
    recordType: recordType ?? null,
    steps,
    rootStepId: rootId,
    wdkStrategyId: resp.strategyId,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

function flattenTree(
  node: StrategyNode,
  stepsMeta: StrategyResponse["steps"],
  out: Step[],
): void {
  if (node.primaryInput) flattenTree(node.primaryInput, stepsMeta, out);
  if (node.secondaryInput) flattenTree(node.secondaryInput, stepsMeta, out);

  const id = String(node.stepId);
  const meta = stepsMeta[id];

  out.push({
    id,
    displayName: meta?.customName ?? meta?.searchName ?? `Step ${node.stepId}`,
    searchName: meta?.searchName,
    parameters: meta?.searchConfig?.parameters as Record<string, unknown> | undefined,
    resultCount: meta?.estimatedSize ?? null,
    wdkStepId: node.stepId,
    primaryInputStepId: node.primaryInput
      ? String(node.primaryInput.stepId)
      : undefined,
    secondaryInputStepId: node.secondaryInput
      ? String(node.secondaryInput.stepId)
      : undefined,
  });
}
