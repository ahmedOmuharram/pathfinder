import { useState } from "react";
import type { Strategy } from "@pathfinder/shared";

/**
 * Returns a stable strategy for display purposes.
 *
 * During streaming, the backend may temporarily clear the strategy
 * (via `graph_cleared` events) before rebuilding it. This hook caches
 * the last known valid strategy so the graph view doesn't flash.
 *
 * The cache resets when switching to a different conversation (new non-null ID).
 * It does NOT reset when the strategy becomes null (temporary clear).
 *
 * Uses the "adjust state during render" pattern recommended by React 19:
 * https://react.dev/reference/react/useState#storing-information-from-previous-renders
 */
export function useStableGraph(strategy: Strategy | null): {
  displayStrategy: Strategy | null;
  hasGraph: boolean;
} {
  const [cached, setCached] = useState<Strategy | null>(null);
  const [prevId, setPrevId] = useState<string | null>(null);

  const currentId = strategy?.id ?? null;
  const hasSteps = !!(strategy && strategy.steps.length > 0);

  // Only clear cache when switching to a DIFFERENT conversation (new non-null ID).
  // Don't clear when strategy becomes null (temporary clear during streaming).
  if (currentId !== null && currentId !== prevId) {
    setPrevId(currentId);
    setCached(null);
  }

  // Cache any strategy that has steps.
  if (hasSteps && cached !== strategy) {
    setCached(strategy);
  }

  const displayStrategy = hasSteps ? strategy : cached;
  const hasGraph = !!(displayStrategy && displayStrategy.steps.length > 0);

  return { displayStrategy, hasGraph };
}
