/**
 * compactLayout — produces a flat "spine" layout for the compact
 * VEuPathDB-style strategy strip.
 *
 * Walks the primary-input chain from root to leftmost leaf, producing
 * a flat list of segments. Each combine segment includes its secondary
 * input step shown above the main row.
 */

import type { Step, StepKind } from "@pathfinder/shared";
import { inferStepKind } from "@/lib/strategyGraph";

// Public types

export interface CompactStep {
  id: string;
  displayName: string;
  kind: StepKind;
  estimatedSize?: number | null;
  recordType?: string | null;
  operator?: string | null;
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
interface SpineSegment {
  step: CompactStep;
  /** Present only for combines: the secondary input shown above. */
  secondaryInput?: CompactStep;
}

// Helpers

function toCompact(step: Step, stepNumber: number): CompactStep {
  const compact: CompactStep = {
    id: step.id,
    displayName: step.displayName ?? "",
    kind: inferStepKind(step),
    stepNumber,
  };
  if (step.estimatedSize != null) {
    compact.estimatedSize = step.estimatedSize;
  }
  if (step.recordType != null) {
    compact.recordType = step.recordType;
  }
  if (step.operator != null) {
    compact.operator = step.operator;
  }
  return compact;
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
  if (steps.length === 0 || rootStepId == null || rootStepId === "") return [];

  const byId = new Map(steps.map((s) => [s.id, s]));

  // Topological sort for step numbers (leaf-first)
  const visited = new Set<string>();
  const ordered: Step[] = [];

  function topo(id: string) {
    if (visited.has(id)) return;
    visited.add(id);
    const step = byId.get(id);
    if (!step) return;
    if (step.primaryInputStepId != null && step.primaryInputStepId !== "")
      topo(step.primaryInputStepId);
    if (step.secondaryInputStepId != null && step.secondaryInputStepId !== "")
      topo(step.secondaryInputStepId);
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
    cur =
      cur.primaryInputStepId != null && cur.primaryInputStepId !== ""
        ? byId.get(cur.primaryInputStepId)
        : undefined;
  }
  spine.reverse(); // now left-to-right

  // Build segments
  return spine.map((step): SpineSegment => {
    const compact = toCompact(step, stepNumbers.get(step.id) ?? 0);
    const kind = inferStepKind(step);

    if (
      kind === "combine" &&
      step.secondaryInputStepId != null &&
      step.secondaryInputStepId !== ""
    ) {
      const sec = byId.get(step.secondaryInputStepId);
      const segment: SpineSegment = { step: compact };
      if (sec != null) {
        segment.secondaryInput = toCompact(sec, stepNumbers.get(sec.id) ?? 0);
      }
      return segment;
    }

    return { step: compact };
  });
}
