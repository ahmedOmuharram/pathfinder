import { useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { useDebounce } from "use-debounce";
import type { StrategyPlan } from "@pathfinder/shared";

type StepCountsResponse = { counts?: Record<string, number | null> };

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
  const [debouncedPlanHash] = useDebounce(planHash, debounceMs);

  const { data } = useQuery({
    queryKey: ["strategies", "step-counts", siteId, debouncedPlanHash] as const,
    queryFn: () => fetchCounts(siteId, plan!),
    enabled: planValid && stepIds.length > 0 && debouncedPlanHash != null,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  const countsKey = JSON.stringify(data?.counts ?? {}) + "|" + stepIds.join(",");
  const validKey = `${planValid}|${stepIds.join(",")}`;

  const [prevCountsKey, setPrevCountsKey] = useState(countsKey);
  if (countsKey !== prevCountsKey) {
    setPrevCountsKey(countsKey);
    const next: Record<string, number | null> = {};
    const counts = data?.counts ?? {};
    for (const stepId of stepIds) {
      next[stepId] = counts[stepId] ?? null;
    }
    setStepCounts(next);
  }

  const [prevValidKey, setPrevValidKey] = useState(validKey);
  if (validKey !== prevValidKey) {
    setPrevValidKey(validKey);
    if (!planValid && stepIds.length > 0) {
      const next: Record<string, number | null> = {};
      for (const stepId of stepIds) next[stepId] = null;
      setStepCounts(next);
    }
  }
}
