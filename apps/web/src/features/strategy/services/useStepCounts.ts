import { useEffect, useRef } from "react";

export type StepCountsResponse = { counts?: Record<string, number | null> };

export function useStepCounts(args: {
  siteId: string;
  plan: unknown | null;
  planHash: string | null;
  stepIds: string[];
  setStepCounts: (counts: Record<string, number | null | undefined>) => void;
  fetchCounts: (siteId: string, plan: any) => Promise<StepCountsResponse>;
  debounceMs?: number;
}) {
  const {
    siteId,
    plan,
    planHash,
    stepIds,
    setStepCounts,
    fetchCounts,
    debounceMs = 650,
  } = args;

  const lastPlanHashRef = useRef<string | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    if (!plan || !planHash) return;
    if (stepIds.length === 0) return;
    if (lastPlanHashRef.current === planHash) return;

    const timeout = window.setTimeout(() => {
      lastPlanHashRef.current = planHash;
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
  }, [siteId, plan, planHash, stepIds, setStepCounts, fetchCounts, debounceMs]);
}

