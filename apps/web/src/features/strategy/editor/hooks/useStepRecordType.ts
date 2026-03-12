"use client";

import { useCallback, useEffect, useMemo, useState, startTransition } from "react";
import type { RecordType } from "@pathfinder/shared";
import { getRecordTypes } from "@/lib/api/sites";
import { normalizeRecordType } from "@/lib/utils/normalizeRecordType";

interface UseStepRecordTypeArgs {
  siteId: string;
  /** The record type passed in from the parent (strategy-level). */
  recordType: string | null;
  /** Initial record type value from the step. */
  initialRecordType: string | null | undefined;
}

export function useStepRecordType({
  siteId,
  recordType,
  initialRecordType,
}: UseStepRecordTypeArgs) {
  const [recordTypeValue, setRecordTypeValue] = useState(
    normalizeRecordType(initialRecordType || recordType),
  );
  const [recordTypeOptions, setRecordTypeOptions] = useState<RecordType[]>([]);
  const [recordTypeFilter, setRecordTypeFilter] = useState("");

  const normalizedRecordTypeValue = normalizeRecordType(recordTypeValue);
  const apiRecordTypeValue = normalizedRecordTypeValue;

  // -------------------------------------------------------------------------
  // Data fetching: record types
  // -------------------------------------------------------------------------
  useEffect(() => {
    let isActive = true;
    getRecordTypes(siteId)
      .then((results) => {
        if (!isActive) return;
        const options = (results || [])
          .filter((item): item is RecordType => Boolean(item && item.name))
          .sort((a, b) =>
            (a.displayName || a.name).localeCompare(b.displayName || b.name),
          );
        setRecordTypeOptions(options);
      })
      .catch((err) => {
        console.error("[StepEditor.loadRecordTypes]", err);
        if (!isActive) return;
        setRecordTypeOptions([]);
      });
    return () => {
      isActive = false;
    };
  }, [siteId]);

  // Validate record type against available options
  useEffect(() => {
    if (recordTypeOptions.length === 0) return;
    if (!recordTypeValue) return;
    const normalized = normalizeRecordType(recordTypeValue);
    const exists = recordTypeOptions.some((option) => option.name === normalized);
    if (!exists) {
      startTransition(() => {
        setRecordTypeValue("");
      });
    }
  }, [recordTypeOptions, recordTypeValue]);

  const resolveRecordTypeForSearch = useCallback(
    (searchRecordType?: string | null) => {
      const normalized = normalizeRecordType(searchRecordType || "");
      if (normalized) {
        const exists = recordTypeOptions.some((option) => option.name === normalized);
        if (exists) return normalized;
      }
      return normalizeRecordType(recordTypeValue || recordType) || "";
    },
    [recordType, recordTypeOptions, recordTypeValue],
  );

  const filteredRecordTypes = useMemo(() => {
    const query = recordTypeFilter.trim().toLowerCase();
    if (!query) return recordTypeOptions;
    return recordTypeOptions.filter((option) => {
      const label = (option.displayName || option.name).toLowerCase();
      return label.includes(query) || option.name.toLowerCase().includes(query);
    });
  }, [recordTypeFilter, recordTypeOptions]);

  return {
    recordTypeValue,
    setRecordTypeValue,
    normalizedRecordTypeValue,
    apiRecordTypeValue,
    recordTypeFilter,
    setRecordTypeFilter,
    recordTypeOptions,
    filteredRecordTypes,
    resolveRecordTypeForSearch,
  };
}
