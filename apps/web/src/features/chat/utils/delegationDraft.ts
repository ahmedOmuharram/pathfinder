import type { PlanningArtifact } from "@pathfinder/shared";
import { isRecord } from "@/lib/utils/isRecord";

type DelegationDraft = {
  goal?: string;
  plan?: unknown;
};

export function getDelegationDraft(
  artifacts: PlanningArtifact[],
): DelegationDraft | null {
  const draft = artifacts.find((a) => a.id === "delegation_draft");
  if (!draft) return null;
  const params = isRecord(draft.parameters) ? draft.parameters : {};
  const goalVal = params["delegationGoal"];
  const goal =
    typeof goalVal === "string" && goalVal.trim() !== "" ? goalVal : undefined;
  const plan = params["delegationPlan"];
  return {
    ...(goal != null ? { goal } : {}),
    ...(plan != null ? { plan } : {}),
  };
}

export function buildDelegationExecutorMessage(draft: DelegationDraft): string {
  const goal = typeof draft.goal === "string" ? draft.goal : "";
  const planText = JSON.stringify(draft.plan ?? {}, null, 2);
  return [
    "Build this strategy using delegation.",
    "",
    "You MUST call `delegate_strategy_subtasks(goal, plan)` with the JSON below.",
    "Use any per-task `context` fields as required parameters/constraints.",
    "",
    "Goal:",
    goal,
    "",
    "Delegation plan (JSON):",
    "```",
    planText,
    "```",
  ].join("\n");
}
