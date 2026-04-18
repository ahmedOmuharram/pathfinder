import { useQuery } from "@tanstack/react-query";
import type { RecordDetail, WdkRecord } from "@/lib/types/wdk";
import { getRecordDetail, type EntityRef } from "@/features/analysis/api/stepResults";

interface UseResultsTableDetailArgs {
  entityRef: EntityRef;
  expandedKey: string | null;
  recordId: WdkRecord["id"] | null;
}

interface ResultsTableDetailState {
  detail: RecordDetail | null;
  detailError: string | null;
  detailLoading: boolean;
}

export function useResultsTableDetail({
  entityRef,
  expandedKey,
  recordId,
}: UseResultsTableDetailArgs): ResultsTableDetailState {
  const enabled = expandedKey != null && recordId != null;

  const { data, error, isPending } = useQuery({
    queryKey: [
      "experiments",
      "records",
      entityRef.type,
      entityRef.id,
      { detail: true, key: expandedKey },
    ] as const,
    queryFn: () => {
      if (recordId == null) {
        throw new Error("recordId must be set when fetching detail");
      }
      return getRecordDetail(entityRef, recordId);
    },
    enabled,
  });

  return {
    detail: data ?? null,
    detailError: error
      ? error instanceof Error
        ? error.message
        : "Failed to load record details"
      : null,
    detailLoading: isPending && enabled,
  };
}
