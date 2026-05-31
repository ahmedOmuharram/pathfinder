import type { Step } from "@pathfinder/shared";

export function patchSteps(steps: Step[], stepId: string, p: Partial<Step>): Step[] {
  return steps.map((s) => (s.id === stepId ? { ...s, ...p } : s));
}
