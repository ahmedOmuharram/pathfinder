import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { WdkRecord, RecordDetail } from "@/lib/types/wdk";
import { getRecordDetail, type EntityRef } from "@/features/analysis/api/stepResults";

interface ResultsTableDetailState {
  expandedKey: string | null;
  detail: RecordDetail | null;
  detailError: string | null;
  detailLoading: boolean;
  handleExpandRow: (key: string, recordId: WdkRecord["id"]) => void;
}

export function useResultsTableDetail(entityRef: EntityRef): ResultsTableDetailState {
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [recordId, setRecordId] = useState<WdkRecord["id"] | null>(null);

  const { data, error, isPending } = useQuery({
    queryKey: ["experiments", "records", entityRef.type, entityRef.id, { detail: true, key: expandedKey }] as const,
    queryFn: () => getRecordDetail(entityRef, recordId!),
    enabled: expandedKey != null && recordId != null,
  });

  const handleExpandRow = (key: string, id: WdkRecord["id"]) => {
    if (expandedKey === key) {
      setExpandedKey(null);
      setRecordId(null);
    } else {
      setExpandedKey(key);
      setRecordId(id);
    }
  };

  return {
    expandedKey,
    detail: data ?? null,
    detailError: error
      ? (error instanceof Error ? error.message : "Failed to load record details")
      : null,
    detailLoading: isPending && expandedKey != null,
    handleExpandRow,
  };
}
