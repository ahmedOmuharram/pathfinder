import { useState, useCallback } from "react";
import type { WdkRecord } from "@/lib/types/wdk";
import { getRecords, type EntityRef } from "@/features/analysis/api/stepResults";

interface DistributionModalState {
  modalValue: string | null;
  modalRecords: WdkRecord[];
  loadingModal: boolean;
  handleBarClick: (value: string) => void;
  closeModal: () => void;
}

export function useDistributionModal(
  entityRef: EntityRef,
  selectedAttr: string,
): DistributionModalState {
  const [modalValue, setModalValue] = useState<string | null>(null);
  const [modalRecords, setModalRecords] = useState<WdkRecord[]>([]);
  const [loadingModal, setLoadingModal] = useState(false);

  const handleBarClickAsync = useCallback(
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
    modalValue,
    modalRecords,
    loadingModal,
    handleBarClick: (value: string) => {
      void handleBarClickAsync(value);
    },
    closeModal,
  };
}
