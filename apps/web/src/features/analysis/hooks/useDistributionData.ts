import { useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { DistributionResponse } from "@/lib/types/wdk";
import { distributionOptions, type EntityRef } from "@/features/analysis/api/stepResults";
import type { DistributionEntry } from "@/features/analysis/components/DistributionExplorer/types";
import { APIError } from "@/lib/api/http";

const NO_DATA_MESSAGE =
  "No distribution data available for this attribute. Try a different one.";

export function parseDistribution(raw: DistributionResponse): DistributionEntry[] {
  const isNumericBinned = raw.histogram[0]?.binStart !== "";
  const parsed = raw.histogram
    .filter((bin) => bin.value > 0)
    .map((bin) => ({
      value: bin.binLabel || bin.binStart,
      count: bin.value,
    }));
  return isNumericBinned ? parsed : parsed.sort((a, b) => b.count - a.count);
}

function formatDistributionError(error: Error): string {
  if (error instanceof APIError && (error.status === 404 || error.status === 422)) {
    return NO_DATA_MESSAGE;
  }
  return error.message;
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
  const queryClient = useQueryClient();

  const distOpts = distributionOptions(entityRef, selectedAttr);

  const { data, isPending, error } = useQuery({
    ...distOpts,
    select: parseDistribution,
  });

  const distribution = data ?? [];

  const errorMessage =
    error !== null
      ? formatDistributionError(error)
      : distribution.length === 0 && !isPending && selectedAttr !== ""
        ? NO_DATA_MESSAGE
        : null;

  const refresh = useCallback(() => {
    void queryClient.invalidateQueries({
      queryKey: distOpts.queryKey,
    });
  }, [queryClient, distOpts.queryKey]);

  return {
    distribution,
    loading: isPending && selectedAttr !== "",
    error: errorMessage,
    refresh,
  };
}
