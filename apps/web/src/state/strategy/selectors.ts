import type { Step } from "@pathfinder/shared";
import { useStrategyStore } from "./store";

const EMPTY_STEPS_BY_ID: Record<string, Step> = Object.freeze({});

/**
 * Memoized selector that derives a `stepsById` map from `strategy.steps`.
 *
 * Uses Zustand's selector caching: identity changes only when the strategy's
 * steps array identity changes. The map is derived (never stored) so it
 * cannot drift from `strategy.steps`.
 */
export function useStepsById(): Record<string, Step> {
  return useStrategyStore((s) => {
    const steps = s.strategy?.steps;
    if (!steps || steps.length === 0) return EMPTY_STEPS_BY_ID;
    return getCachedStepsById(steps);
  });
}

const STEPS_CACHE = new WeakMap<readonly Step[], Record<string, Step>>();

function getCachedStepsById(steps: readonly Step[]): Record<string, Step> {
  const cached = STEPS_CACHE.get(steps);
  if (cached) return cached;
  const map: Record<string, Step> = {};
  for (const s of steps) {
    map[s.id] = s;
  }
  STEPS_CACHE.set(steps, map);
  return map;
}
