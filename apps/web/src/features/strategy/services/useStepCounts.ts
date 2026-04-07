import { useEffect, useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import type { StrategyPlan } from "@pathfinder/shared";

type StepCountsResponse = { counts?: Record<string, number | null> };

/**
 * Debounces a value by `ms`. Returns the last stable value after the delay.
 */
function useDebouncedValue<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

export function useStepCounts(args: {
  siteId: string;
  plan: StrategyPlan | null;
  planHash: string | null;
  stepIds: string[];
  setStepCounts: (counts: Record<string, number | null | undefined>) => void;
  fetchCounts: (siteId: string, plan: StrategyPlan) => Promise<StepCountsResponse>;
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

  const planValid = plan != null && planHash != null && planHash !== "";
  const debouncedPlanHash = useDebouncedValue(planHash, debounceMs);

  const { data } = useQuery({
    queryKey: ["strategies", "step-counts", siteId, debouncedPlanHash] as const,
    queryFn: () => fetchCounts(siteId, plan!),
    enabled: planValid && stepIds.length > 0 && debouncedPlanHash != null,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  // Write TQ data to the strategy store so graph nodes can read it.
  useEffect(() => {
    const next: Record<string, number | null> = {};
    const counts = data?.counts ?? {};
    for (const stepId of stepIds) {
      next[stepId] = counts[stepId] ?? null;
    }
    setStepCounts(next);
  }, [data, stepIds, setStepCounts]);

  // When plan is invalid, immediately show null counts.
  useEffect(() => {
    if (planValid || stepIds.length === 0) return;
    const next: Record<string, number | null> = {};
    for (const stepId of stepIds) next[stepId] = null;
    setStepCounts(next);
  }, [planValid, stepIds, setStepCounts]);
}
