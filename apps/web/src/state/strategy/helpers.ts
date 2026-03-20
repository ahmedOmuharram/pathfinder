/**
 * Pure helper functions shared across strategy slices.
 */

import type { Step, Strategy } from "@pathfinder/shared";
import { DEFAULT_STREAM_NAME } from "@pathfinder/shared";
import { getRootSteps, getRootStepId } from "@/lib/strategyGraph";

/** Build a Record<string, Step> from an array. */
export function buildStepsById(steps: Step[]): Record<string, Step> {
  const result: Record<string, Step> = {};
  for (const step of steps) {
    result[step.id] = step;
  }
  return result;
}

/** Derive a Strategy object from the step map and optional existing metadata. */
export function buildStrategy(
  stepsById: Record<string, Step>,
  existing: Strategy | null,
): Strategy | null {
  const steps = Object.values(stepsById);
  if (steps.length === 0) return null;

  const roots = getRootSteps(steps);
  const rootStepId = roots.length === 1 ? getRootStepId(steps) : null;

  return {
    id: existing?.id ?? "draft",
    name: existing?.name ?? DEFAULT_STREAM_NAME,
    siteId: existing?.siteId ?? "veupathdb",
    recordType: existing?.recordType ?? steps[0]?.recordType ?? "gene",
    steps,
    rootStepId,
    wdkStrategyId: existing?.wdkStrategyId ?? null,
    wdkUrl: existing?.wdkUrl ?? null,
    isSaved: existing?.isSaved ?? false,
    description: existing?.description ?? null,
    createdAt: existing?.createdAt ?? new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

/** Normalize a strategy id, generating a fallback for missing ids. */
export function normalizeStrategyId(strategy: Strategy): string {
  if (strategy.id) {
    return String(strategy.id);
  }
  return `executed-${Date.now()}`;
}
