import { useState, useEffect, useCallback } from "react";
import type { DistributionResponse } from "@/lib/types/wdk";
import { getDistribution, type EntityRef } from "@/features/analysis/api/stepResults";
import type { DistributionEntry } from "@/features/analysis/components/DistributionExplorer/types";

export function parseDistribution(raw: DistributionResponse): DistributionEntry[] {
  if (Array.isArray(raw.histogram)) {
    const isNumericBinned = raw.histogram[0]?.binStart != null;
    const parsed = raw.histogram
      .filter((bin) => bin.value > 0)
      .map((bin) => ({
        value: bin.binLabel ?? bin.binStart ?? "",
        count: bin.value,
      }));
    return isNumericBinned ? parsed : parsed.sort((a, b) => b.count - a.count);
  }

  const histogram = raw.distribution ?? raw;
  return Object.entries(histogram)
    .filter(([key]) => key !== "total" && key !== "attributeName")
    .map(([value, count]) => ({ value, count: Number(count) || 0 }))
    .sort((a, b) => b.count - a.count);
}

function applyDistributionResult(
  raw: DistributionResponse,
  setDistribution: (entries: DistributionEntry[]) => void,
  setError: (error: string | null) => void,
): void {
  const entries = parseDistribution(raw);
  if (entries.length === 0) {
    setError("No distribution data available for this attribute. Try a different one.");
    setDistribution([]);
  } else {
    setDistribution(entries);
    setError(null);
  }
}

function handleDistributionError(
  err: unknown,
  setError: (error: string | null) => void,
): void {
  const msg = err instanceof Error ? err.message : String(err);
  const lower = msg.toLowerCase();
  if (lower.includes("422") || lower.includes("404") || lower.includes("not found")) {
    setError("No distribution data available for this attribute. Try a different one.");
  } else {
    setError(msg);
  }
}

interface DistributionDataState {
  distribution: DistributionEntry[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useDistributionData(
  entityRef: EntityRef,
  selectedAttr: string,
): DistributionDataState {
  const [distribution, setDistribution] = useState<DistributionEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshCounter, setRefreshCounter] = useState(0);

  useEffect(() => {
    if (!selectedAttr) return;
    let cancelled = false;

    const fetchData = async (): Promise<void> => {
      setLoading(true);
      setError(null);
      try {
        const raw = await getDistribution(entityRef, selectedAttr);
        if (!cancelled) applyDistributionResult(raw, setDistribution, setError);
      } catch (err) {
        if (!cancelled) handleDistributionError(err, setError);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void fetchData();

    return () => {
      cancelled = true;
    };
  }, [selectedAttr, entityRef, refreshCounter]);

  const refresh = useCallback(() => {
    setRefreshCounter((c) => c + 1);
  }, []);

  return {
    distribution,
    loading,
    error,
    refresh,
  };
}
