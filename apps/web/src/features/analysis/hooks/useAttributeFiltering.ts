import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { RecordAttribute } from "@/lib/types/wdk";
import { attributesOptions, type EntityRef } from "@/features/analysis/api/stepResults";
import { isDistributableAttr } from "@/features/analysis/components/DistributionExplorer/attributeFilters";

interface AttributeFilteringState {
  attributes: RecordAttribute[];
  selectedAttr: string;
  setSelectedAttr: (attr: string) => void;
  loading: boolean;
  error: string | null;
}

export function useAttributeFiltering(entityRef: EntityRef): AttributeFilteringState {
  const [selectedAttr, setSelectedAttr] = useState("");

  const { data, isPending, error } = useQuery({
    ...attributesOptions(entityRef),
    select: (raw) => raw.attributes.filter(isDistributableAttr),
  });

  const attributes = useMemo(() => data ?? [], [data]);

  // Auto-select first distributable attribute when data loads or entityRef changes.
  const firstAttrName = attributes[0]?.name ?? "";
  useEffect(() => {
    setSelectedAttr(firstAttrName);
  }, [firstAttrName]);

  return {
    attributes,
    selectedAttr,
    setSelectedAttr,
    loading: isPending,
    error: error != null ? (error instanceof Error ? error.message : String(error)) : null,
  };
}
