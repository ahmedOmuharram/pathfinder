import { stableStringify } from "./planParameterEditorUtils";

export function storedValuesEqual(left: unknown, right: unknown): boolean {
  return stableStringify(left) === stableStringify(right);
}

export function collectParamEdits(
  localParamEdits: Record<string, Record<string, unknown>>,
): Array<{ stepId: string; paramName: string; newValue: unknown }> {
  const collected: Array<{
    stepId: string;
    paramName: string;
    newValue: unknown;
  }> = [];
  for (const [stepId, params] of Object.entries(localParamEdits)) {
    for (const [paramName, newValue] of Object.entries(params)) {
      collected.push({ stepId, paramName, newValue });
    }
  }
  return collected;
}

export function collectAnswers(
  localAnswers: Record<string, unknown>,
): Array<{ questionId: string; answer: unknown }> {
  return Object.entries(localAnswers).map(([questionId, answer]) => ({
    questionId,
    answer,
  }));
}
