import { useEffect, useRef } from "react";
import type { StrategyPlan } from "@pathfinder/shared";

export type StepCountsResponse = { counts?: Record<string, number | null> };

export function useStepCounts(args: {
  siteId: string;
  plan: StrategyPlan | null;
  planHash: string | null;
  stepIds: string[];
  setStepCounts: (counts: Record<string, number | null | undefined>) => void;
  fetchCounts: (siteId: string, plan: StrategyPlan) => Promise<StepCountsResponse>;
  debounceMs?: number;
  /** Increment to force a re-fetch even when planHash hasn't changed. */
  refreshKey?: number;
}) {
  const {
    siteId,
    plan,
    planHash,
    stepIds,
    setStepCounts,
    fetchCounts,
    debounceMs = 650,
    refreshKey = 0,
  } = args;

  const lastRequestKeyRef = useRef<string | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    if (stepIds.length === 0) return;

    // If the graph/plan is currently invalid (e.g. multiple outputs), don't wait on
    // step counts at all. Immediately show unknown counts ("?") and invalidate any
    // in-flight request so it can't overwrite the UI later.
    if (!plan || !planHash) {
      requestIdRef.current += 1;
      lastRequestKeyRef.current = null;
      const next: Record<string, number | null> = {};
      for (const stepId of stepIds) next[stepId] = null;
      setStepCounts(next);
      return;
    }

    const stepIdsKey = stepIds.slice().sort().join("|");
    const requestKey = `${planHash}:${stepIdsKey}:${refreshKey}`;
    if (lastRequestKeyRef.current === requestKey) return;

    const timeout = window.setTimeout(() => {
      lastRequestKeyRef.current = requestKey;
      const requestId = (requestIdRef.current += 1);

      const loading: Record<string, number | null | undefined> = {};
      for (const stepId of stepIds) loading[stepId] = undefined;
      setStepCounts(loading);

      fetchCounts(siteId, plan)
        .then((response) => {
          if (requestId !== requestIdRef.current) return;
          const counts = response.counts || {};
          const next: Record<string, number | null> = {};
          for (const stepId of stepIds) {
            next[stepId] = counts[stepId] ?? null;
          }
          setStepCounts(next);
        })
        .catch(() => {
          if (requestId !== requestIdRef.current) return;
          const next: Record<string, number | null> = {};
          for (const stepId of stepIds) next[stepId] = null;
          setStepCounts(next);
        });
    }, debounceMs);

    return () => window.clearTimeout(timeout);
  }, [
    siteId,
    plan,
    planHash,
    stepIds,
    setStepCounts,
    fetchCounts,
    debounceMs,
    refreshKey,
  ]);
}
