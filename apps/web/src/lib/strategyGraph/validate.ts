import type { Step } from "./types";

export type StrategyGraphError = {
  code:
    | "MISSING_INPUT"
    | "UNKNOWN_STEP"
    | "MISSING_OPERATOR"
    | "MISSING_SEARCH_NAME"
    | "ORPHAN_STEP"
    | "MULTIPLE_ROOTS";
  message: string;
  stepId?: string;
  inputStepId?: string;
};

export type CombineRecordTypeMismatch = {
  stepId: string;
  leftType: string | null;
  rightType: string | null;
};

export type CombineMismatchGroup = {
  id: string;
  ids: Set<string>;
  message: string;
};

function inferKind(step: Step): "search" | "transform" | "combine" | "invalid" {
  if (step.secondaryInputStepId && !step.primaryInputStepId) return "invalid";
  if (step.primaryInputStepId && step.secondaryInputStepId) return "combine";
  // A step with an operator (or explicit kind="combine") is a combine even if
  // one or both inputs were removed.  This ensures combine-specific checks
  // (two inputs required, operator required, etc.) still fire.
  if (step.operator || step.kind === "combine") return "combine";
  if (step.primaryInputStepId) return "transform";
  return "search";
}

export function resolveRecordType(
  stepId: string | undefined,
  stepsMap: Map<string, Step>,
): string | null {
  if (!stepId) return null;
  const step = stepsMap.get(stepId);
  if (!step) return null;
  if (step.recordType) return step.recordType;
  const kind = inferKind(step);
  if (kind === "transform" && step.primaryInputStepId) {
    return resolveRecordType(step.primaryInputStepId, stepsMap);
  }
  if (kind === "combine") {
    const left = resolveRecordType(step.primaryInputStepId, stepsMap);
    const right = resolveRecordType(step.secondaryInputStepId, stepsMap);
    if (left && right && left !== right) return "__mismatch__";
    return left || right || null;
  }
  return null;
}

export function findCombineRecordTypeMismatch(
  stepsList: Step[],
): CombineRecordTypeMismatch | null {
  const stepsMap = new Map(stepsList.map((step) => [step.id, step]));
  for (const step of stepsList) {
    if (inferKind(step) !== "combine") continue;
    const leftType = resolveRecordType(step.primaryInputStepId, stepsMap);
    const rightType = resolveRecordType(step.secondaryInputStepId, stepsMap);
    if (
      leftType &&
      rightType &&
      leftType !== rightType &&
      leftType !== "__mismatch__" &&
      rightType !== "__mismatch__"
    ) {
      return { stepId: step.id, leftType, rightType };
    }
    if (leftType === "__mismatch__" || rightType === "__mismatch__") {
      return { stepId: step.id, leftType, rightType };
    }
  }
  return null;
}

export function getRootSteps(steps: Step[]): Step[] {
  if (steps.length === 0) return [];
  const referenced = new Set<string>();
  for (const step of steps) {
    if (step.primaryInputStepId) referenced.add(step.primaryInputStepId);
    if (step.secondaryInputStepId) referenced.add(step.secondaryInputStepId);
  }
  return steps.filter((step) => !referenced.has(step.id));
}

export function getRootStepId(steps: Step[]): string | null {
  if (steps.length === 0) return null;
  const roots = getRootSteps(steps);
  // Single-output invariant: a valid graph must have exactly one root.
  // When the graph is invalid (0 or multiple roots), do not guess a root.
  if (roots.length !== 1) return null;
  return roots[0].id;
}

export function getCombineMismatchGroups(steps: Step[]): CombineMismatchGroup[] {
  if (steps.length === 0) return [];
  const stepsMap = new Map(steps.map((step) => [step.id, step]));
  const groups: CombineMismatchGroup[] = [];
  for (const step of steps) {
    if (inferKind(step) !== "combine") continue;
    const leftType = resolveRecordType(step.primaryInputStepId, stepsMap);
    const rightType = resolveRecordType(step.secondaryInputStepId, stepsMap);
    if (!leftType || !rightType) continue;
    if (
      leftType === "__mismatch__" ||
      rightType === "__mismatch__" ||
      leftType !== rightType
    ) {
      const ids = new Set<string>([step.id]);
      if (step.primaryInputStepId) ids.add(step.primaryInputStepId);
      if (step.secondaryInputStepId) ids.add(step.secondaryInputStepId);
      groups.push({
        id: step.id,
        ids,
        message: "Cannot combine steps with different record types.",
      });
    }
  }
  return groups;
}

export function validateStrategySteps(steps: Step[]): StrategyGraphError[] {
  const errors: StrategyGraphError[] = [];
  if (steps.length === 0) return errors;

  const stepIds = new Set(steps.map((step) => step.id));
  const referenced = new Set<string>();

  for (const step of steps) {
    const kind = inferKind(step);
    // Combine steps use a canonical searchName ("boolean_question") during serialization;
    // the UI doesn't store this on the step, so don't block on it here.
    if (!step.searchName && kind !== "combine") {
      errors.push({
        code: "MISSING_SEARCH_NAME",
        message: "searchName is required.",
        stepId: step.id,
      });
    }

    if (kind === "invalid") {
      errors.push({
        code: "MISSING_INPUT",
        message: "secondaryInput requires primaryInput.",
        stepId: step.id,
      });
    }

    if (kind === "combine") {
      if (!step.operator) {
        errors.push({
          code: "MISSING_OPERATOR",
          message: "Combine steps require an operator.",
          stepId: step.id,
        });
      }
      if (step.operator === "COLOCATE" && !step.colocationParams) {
        errors.push({
          code: "MISSING_INPUT",
          message: "COLOCATE requires colocationParams (upstream/downstream/strand).",
          stepId: step.id,
        });
      }
      if (!step.primaryInputStepId || !step.secondaryInputStepId) {
        errors.push({
          code: "MISSING_INPUT",
          message: "Combine steps require two inputs.",
          stepId: step.id,
        });
      }
    }

    if (step.primaryInputStepId) referenced.add(step.primaryInputStepId);
    if (step.secondaryInputStepId) referenced.add(step.secondaryInputStepId);

    if (step.primaryInputStepId && !stepIds.has(step.primaryInputStepId)) {
      errors.push({
        code: "UNKNOWN_STEP",
        message: "Primary input step does not exist.",
        stepId: step.id,
        inputStepId: step.primaryInputStepId,
      });
    }
    if (step.secondaryInputStepId && !stepIds.has(step.secondaryInputStepId)) {
      errors.push({
        code: "UNKNOWN_STEP",
        message: "Secondary input step does not exist.",
        stepId: step.id,
        inputStepId: step.secondaryInputStepId,
      });
    }
  }

  const roots = getRootSteps(steps);
  if (roots.length === 0) {
    errors.push({
      code: "ORPHAN_STEP",
      message: "Strategy graph has no root steps.",
    });
  } else if (roots.length > 1) {
    errors.push({
      code: "MULTIPLE_ROOTS",
      message: "Strategy graph must have a single final output step.",
    });
  }

  return errors;
}
