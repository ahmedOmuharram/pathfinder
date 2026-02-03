import type { StepKind } from "@pathfinder/shared";

type StepLike = {
  kind?: StepKind;
  primaryInputStepId?: string;
  secondaryInputStepId?: string;
};

export function inferStepKind(step: StepLike): StepKind {
  if (step.kind) return step.kind;
  if (step.primaryInputStepId && step.secondaryInputStepId) return "combine";
  if (step.primaryInputStepId) return "transform";
  return "search";
}

