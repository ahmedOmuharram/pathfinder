/**
 * Pure helpers for annotating steps with validation errors and result counts.
 *
 * Extracted from draftSlice so the batch-update-with-change-detection
 * logic is independently testable and the slice stays focused on
 * structural step CRUD and strategy building.
 */

import type { Step } from "@pathfinder/shared";

/**
 * Apply validation error updates to the step map.
 *
 * Returns a new step map if any step changed, or `null` if nothing changed
 * (callers can short-circuit the Zustand `set` call).
 */
export function applyStepValidationErrors(
  stepsById: Record<string, Step>,
  errors: Record<string, string | undefined>,
): Record<string, Step> | null {
  let changed = false;
  const next = { ...stepsById };
  for (const [stepId, message] of Object.entries(errors)) {
    const step = next[stepId];
    if (!step) continue;
    const nextMessage = message ?? null;
    if (step.validationError !== nextMessage) {
      next[stepId] = { ...step, validationError: nextMessage };
      changed = true;
    }
  }
  return changed ? next : null;
}

/**
 * Apply result count updates to the step map.
 *
 * Returns a new step map if any step changed, or `null` if nothing changed.
 */
export function applyStepCounts(
  stepsById: Record<string, Step>,
  counts: Record<string, number | null | undefined>,
): Record<string, Step> | null {
  let changed = false;
  const next = { ...stepsById };
  for (const [stepId, count] of Object.entries(counts)) {
    const step = next[stepId];
    if (!step) continue;
    const nextCount = typeof count === "number" || count === null ? count : null;
    if (step.resultCount !== nextCount) {
      next[stepId] = { ...step, resultCount: nextCount };
      changed = true;
    }
  }
  return changed ? next : null;
}
