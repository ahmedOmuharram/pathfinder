import { useState, useEffect } from "react";
import type { RecordAttribute } from "@/lib/types/wdk";
import { getAttributes, type EntityRef } from "@/features/analysis/api/stepResults";
import { isDistributableAttr } from "@/features/analysis/components/DistributionExplorer/attributeFilters";

interface AttributeFilteringState {
  attributes: RecordAttribute[];
  selectedAttr: string;
  setSelectedAttr: (attr: string) => void;
  loading: boolean;
  error: string | null;
}

export function useAttributeFiltering(entityRef: EntityRef): AttributeFilteringState {
  const [attributes, setAttributes] = useState<RecordAttribute[]>([]);
  const [selectedAttr, setSelectedAttr] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSelectedAttr("");

    getAttributes(entityRef)
      .then(({ attributes: attrs }) => {
        if (cancelled) return;
        const displayable = attrs.filter(isDistributableAttr);
        setAttributes(displayable);
        const first = displayable[0];
        if (first != null) {
          setSelectedAttr(first.name);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityRef.id, entityRef.type]);

  return { attributes, selectedAttr, setSelectedAttr, loading, error };
}
