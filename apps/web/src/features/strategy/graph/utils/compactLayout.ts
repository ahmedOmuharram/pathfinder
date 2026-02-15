/**
 * compactLayout — produces a flat "spine" layout for the compact
 * VEuPathDB-style strategy strip.
 *
 * Walks the primary-input chain from root to leftmost leaf, producing
 * a flat list of segments. Each combine segment includes its secondary
 * input step shown above the main row.
 */

import type { Step, StepKind } from "@pathfinder/shared";

// Public types

export interface CompactStep {
  id: string;
  displayName: string;
  kind: StepKind;
  resultCount?: number | null;
  recordType?: string;
  operator?: string;
  /** 1-based index in the strategy execution order. */
  stepNumber: number;
}

/**
 * One segment of the main horizontal spine.
 *
 * - Regular steps (search / transform): just `step`.
 * - Combines: `step` is the combine result on the main row,
 *   `secondaryInput` is the step shown above the Venn connector.
 */
export interface SpineSegment {
  step: CompactStep;
  /** Present only for combines: the secondary input shown above. */
  secondaryInput?: CompactStep;
}

// Helpers

function inferKind(step: Step): StepKind {
  if (step.kind) return step.kind;
  if (step.primaryInputStepId && step.secondaryInputStepId) return "combine";
  if (step.primaryInputStepId) return "transform";
  return "search";
}

function toCompact(step: Step, stepNumber: number): CompactStep {
  return {
    id: step.id,
    displayName: step.displayName,
    kind: inferKind(step),
    resultCount: step.resultCount,
    recordType: step.recordType,
    operator: step.operator,
    stepNumber,
  };
}

// Layout builder

/**
 * Build a flat spine layout from a step array + rootStepId.
 *
 * 1. Topologically sort all steps to assign step numbers.
 * 2. Walk from root backwards via `primaryInputStepId` to collect
 *    the main spine (reversed to left-to-right).
 * 3. For each combine on the spine, attach the secondary input.
 */
export function buildSpineLayout(
  steps: Step[],
  rootStepId: string | null,
): SpineSegment[] {
  if (!steps.length || !rootStepId) return [];

  const byId = new Map(steps.map((s) => [s.id, s]));

  // Topological sort for step numbers (leaf-first)
  const visited = new Set<string>();
  const ordered: Step[] = [];

  function topo(id: string) {
    if (visited.has(id)) return;
    visited.add(id);
    const step = byId.get(id);
    if (!step) return;
    if (step.primaryInputStepId) topo(step.primaryInputStepId);
    if (step.secondaryInputStepId) topo(step.secondaryInputStepId);
    ordered.push(step);
  }

  topo(rootStepId);

  const stepNumbers = new Map<string, number>();
  ordered.forEach((s, i) => stepNumbers.set(s.id, i + 1));

  // Walk the primary chain from root to leaf
  const spine: Step[] = [];
  let cur = byId.get(rootStepId);
  while (cur) {
    spine.push(cur);
    cur = cur.primaryInputStepId ? byId.get(cur.primaryInputStepId) : undefined;
  }
  spine.reverse(); // now left-to-right

  // Build segments
  return spine.map((step): SpineSegment => {
    const compact = toCompact(step, stepNumbers.get(step.id) ?? 0);
    const kind = inferKind(step);

    if (kind === "combine" && step.secondaryInputStepId) {
      const sec = byId.get(step.secondaryInputStepId);
      return {
        step: compact,
        secondaryInput: sec ? toCompact(sec, stepNumbers.get(sec.id) ?? 0) : undefined,
      };
    }

    return { step: compact };
  });
}
