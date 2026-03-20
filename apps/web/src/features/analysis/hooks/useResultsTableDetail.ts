import { useState, useCallback } from "react";
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
  const [detail, setDetail] = useState<RecordDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const handleExpandRowAsync = useCallback(
    async (key: string, recordId: WdkRecord["id"]) => {
      if (expandedKey === key) {
        setExpandedKey(null);
        setDetail(null);
        setDetailError(null);
        return;
      }
      setExpandedKey(key);
      setDetail(null);
      setDetailError(null);
      setDetailLoading(true);
      try {
        const d = await getRecordDetail(entityRef, recordId);
        setDetail(d);
      } catch (err) {
        setDetail(null);
        setDetailError(
          err instanceof Error ? err.message : "Failed to load record details",
        );
      } finally {
        setDetailLoading(false);
      }
    },
    [entityRef, expandedKey],
  );

  const handleExpandRow = useCallback(
    (key: string, recordId: WdkRecord["id"]) => {
      void handleExpandRowAsync(key, recordId);
    },
    [handleExpandRowAsync],
  );

  return {
    expandedKey,
    detail,
    detailError,
    detailLoading,
    handleExpandRow,
  };
}
