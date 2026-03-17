import { useState, useEffect, useCallback } from "react";
import type { WdkRecord, DistributionResponse } from "@/lib/types/wdk";
import {
  getDistribution,
  getRecords,
  type EntityRef,
} from "@/features/analysis/api/stepResults";
import type { DistributionEntry } from "@/features/analysis/components/DistributionExplorer/types";

export function parseDistribution(raw: DistributionResponse): DistributionEntry[] {
  if (Array.isArray(raw.histogram)) {
    const isNumericBinned =
      raw.histogram.length > 0 && raw.histogram[0].binStart != null;
    const parsed = raw.histogram
      .filter((bin) => bin.value > 0)
      .map((bin) => ({
        value: bin.binLabel || bin.binStart || "",
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

export interface DistributionDataState {
  distribution: DistributionEntry[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
  modalValue: string | null;
  modalRecords: WdkRecord[];
  loadingModal: boolean;
  handleBarClick: (value: string) => void;
  closeModal: () => void;
}

export function useDistributionData(
  entityRef: EntityRef,
  selectedAttr: string,
): DistributionDataState {
  const [distribution, setDistribution] = useState<DistributionEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [modalValue, setModalValue] = useState<string | null>(null);
  const [modalRecords, setModalRecords] = useState<WdkRecord[]>([]);
  const [loadingModal, setLoadingModal] = useState(false);

  const fetchDistribution = useCallback(
    (attrName: string) => {
      if (!attrName) return;
      setLoading(true);
      setError(null);

      getDistribution(entityRef, attrName)
        .then((raw) => {
          const entries = parseDistribution(raw);
          if (entries.length === 0) {
            setError(
              "No distribution data available for this attribute. Try a different one.",
            );
            setDistribution([]);
          } else {
            setDistribution(entries);
          }
        })
        .catch((err) => {
          const msg = err instanceof Error ? err.message : String(err);
          const lower = msg.toLowerCase();
          if (
            lower.includes("422") ||
            lower.includes("404") ||
            lower.includes("not found")
          ) {
            setError(
              "No distribution data available for this attribute. Try a different one.",
            );
          } else {
            setError(msg);
          }
        })
        .finally(() => setLoading(false));
    },
    [entityRef],
  );

  useEffect(() => {
    if (selectedAttr) fetchDistribution(selectedAttr);
  }, [selectedAttr, fetchDistribution]);

  const refresh = useCallback(() => {
    fetchDistribution(selectedAttr);
  }, [selectedAttr, fetchDistribution]);

  const handleBarClick = useCallback(
    async (value: string) => {
      setModalValue(value);
      setModalRecords([]);
      setLoadingModal(true);

      try {
        const { records } = await getRecords(entityRef, {
          attributes: [selectedAttr, "gene_product"],
          filterAttribute: selectedAttr,
          filterValue: value,
          limit: 500,
        });
        setModalRecords(records);
      } catch {
        setModalRecords([]);
      } finally {
        setLoadingModal(false);
      }
    },
    [entityRef, selectedAttr],
  );

  const closeModal = useCallback(() => setModalValue(null), []);

  return {
    distribution,
    loading,
    error,
    refresh,
    modalValue,
    modalRecords,
    loadingModal,
    handleBarClick,
    closeModal,
  };
}
