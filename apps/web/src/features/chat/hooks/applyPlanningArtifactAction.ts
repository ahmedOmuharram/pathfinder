/**
 * Pure async function for applying a planning artifact to a strategy.
 *
 * Extracted from useChatPanelState for testability.
 */

import type { PlanningArtifact, Strategy } from "@pathfinder/shared";
import { getStrategy, updateStrategy } from "@/lib/api/strategies";

export interface ApplyPlanningArtifactDeps {
  setStrategy: (s: Strategy | null) => void;
  setStrategyMeta: (u: Partial<Strategy>) => void;
}

/**
 * Apply a planning artifact's proposed strategy plan to the given strategy.
 *
 * Returns true if the apply succeeded, false otherwise.
 */
export async function applyPlanningArtifactAction(
  strategyId: string,
  artifact: PlanningArtifact,
  deps: ApplyPlanningArtifactDeps,
): Promise<boolean> {
  const plan = artifact.proposedStrategyPlan;
  if (plan == null) return false;

  await updateStrategy(strategyId, { plan });
  const full = await getStrategy(strategyId);
  deps.setStrategy(full);
  deps.setStrategyMeta({
    name: full.name,
    ...(full.description != null ? { description: full.description } : {}),
    ...(full.recordType != null ? { recordType: full.recordType } : {}),
    siteId: full.siteId,
  });
  return true;
}
