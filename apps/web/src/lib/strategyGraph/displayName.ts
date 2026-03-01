import type { StepKind } from "@pathfinder/shared";
import { inferStepKind } from "./kind";

const isUrlLike = (value: string | null | undefined) =>
  typeof value === "string" &&
  (value.startsWith("http://") || value.startsWith("https://"));

export const normalizeName = (value: string | null | undefined) =>
  typeof value === "string" ? value.trim().toLowerCase() : "";

export interface DisplayNameStep {
  kind?: StepKind | string;
  searchName?: string;
  operator?: string;
  primaryInputStepId?: string;
  secondaryInputStepId?: string;
}

export function isFallbackDisplayName(
  name: string | null | undefined,
  step: DisplayNameStep,
): boolean {
  if (!name) return true;
  if (isUrlLike(name)) return true;
  const normalized = normalizeName(name);
  const resolvedKind =
    step.kind ?? inferStepKind(step as Parameters<typeof inferStepKind>[0]);
  const candidates = new Set<string>([
    normalizeName(step.searchName),
    normalizeName(resolvedKind),
  ]);
  if (step.operator) {
    const op = normalizeName(step.operator);
    candidates.add(op);
    candidates.add(`${op} combine`);
  }
  return candidates.has(normalized);
}
