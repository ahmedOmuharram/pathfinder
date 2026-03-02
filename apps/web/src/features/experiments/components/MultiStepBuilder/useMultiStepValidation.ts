import { useMemo } from "react";
import type { PlanStepNode } from "@pathfinder/shared";
import type { MultiStepState } from "./useMultiStepState";

export interface StepWarning {
  stepId: string;
  message: string;
  severity: "warning" | "error";
}

export interface MultiStepValidation {
  canRun: boolean;
  warnings: StepWarning[];
  stepTree: PlanStepNode | null;
}

export function useMultiStepValidation(state: MultiStepState): MultiStepValidation {
  const {
    planResult,
    steps,
    benchmarkMode,
    benchmarkControlSets,
    positiveControls,
    negativeControls,
  } = state;

  const stepTree = useMemo((): PlanStepNode | null => {
    if (!planResult) return null;
    return planResult.plan.root;
  }, [planResult]);

  const canRun = useMemo(() => {
    if (steps.length === 0) return false;
    if (!planResult) return false;
    if (benchmarkMode) {
      return (
        benchmarkControlSets.length > 0 &&
        benchmarkControlSets.some(
          (cs) => cs.positiveControls.length > 0 || cs.negativeControls.length > 0,
        )
      );
    }
    if (positiveControls.length === 0 && negativeControls.length === 0) return false;
    return true;
  }, [
    steps.length,
    positiveControls.length,
    negativeControls.length,
    planResult,
    benchmarkMode,
    benchmarkControlSets,
  ]);

  const warnings = useMemo(() => {
    const w: StepWarning[] = [];
    for (const step of steps) {
      if (step.resultCount === 0) {
        w.push({
          stepId: step.id,
          message: `"${step.displayName}" returns 0 results`,
          severity: "error",
        });
      } else if (typeof step.resultCount === "number" && step.resultCount > 50000) {
        w.push({
          stepId: step.id,
          message: `"${step.displayName}" returns ${step.resultCount.toLocaleString()} results — very broad`,
          severity: "warning",
        });
      }
    }
    return w;
  }, [steps]);

  return { canRun, warnings, stepTree };
}
