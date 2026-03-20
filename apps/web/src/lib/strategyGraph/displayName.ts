import type { StepKind } from "@pathfinder/shared";
import { inferStepKind } from "./kind";

const isUrlLike = (value: string | null | undefined) =>
  typeof value === "string" &&
  (value.startsWith("http://") || value.startsWith("https://"));

export const normalizeName = (value: string | null | undefined) =>
  typeof value === "string" ? value.trim().toLowerCase() : "";

export interface DisplayNameStep {
  kind?: StepKind | string | null;
  searchName?: string | null;
  operator?: string | null;
  primaryInputStepId?: string | null;
  secondaryInputStepId?: string | null;
}

export function isFallbackDisplayName(
  name: string | null | undefined,
  step: DisplayNameStep,
): boolean {
  if (name == null || name === "") return true;
  if (isUrlLike(name)) return true;
  const normalized = normalizeName(name);
  const resolvedKind =
    step.kind ?? inferStepKind(step as Parameters<typeof inferStepKind>[0]);
  const candidates = new Set<string>([
    normalizeName(step.searchName),
    normalizeName(resolvedKind),
  ]);
  if (step.operator != null && step.operator !== "") {
    const op = normalizeName(step.operator);
    candidates.add(op);
    candidates.add(`${op} combine`);
  }
  return candidates.has(normalized);
}
