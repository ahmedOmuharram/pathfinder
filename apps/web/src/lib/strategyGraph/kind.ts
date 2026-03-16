import type { StepKind } from "@pathfinder/shared";

type StepLike = {
  kind?: StepKind | string | null;
  primaryInputStepId?: string | null;
  secondaryInputStepId?: string | null;
  operator?: string | null;
};

export function inferStepKind(step: StepLike): StepKind {
  if (step.kind === "search" || step.kind === "transform" || step.kind === "combine")
    return step.kind;
  if (step.primaryInputStepId && step.secondaryInputStepId) return "combine";
  // A step with an operator is a combine step even if one or both inputs were
  // removed (e.g. the user deleted a node).  Recognising it as "combine"
  // ensures combine-specific validation fires and the UI renders it correctly.
  if (step.operator) return "combine";
  if (step.primaryInputStepId) return "transform";
  return "search";
}
