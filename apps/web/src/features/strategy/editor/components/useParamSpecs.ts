"use client";

import { useEffect, useState } from "react";
import type { ParamSpec, Search } from "@pathfinder/shared";
import { getParamSpecs } from "@/lib/api/client";
import { normalizeRecordType } from "@/features/strategy/recordType";
import { buildContextValues } from "./stepEditorUtils";

type UseParamSpecsArgs = {
  siteId: string;
  recordType: string | null;
  searchName: string;
  selectedSearch: Search | null;
  isSearchNameAvailable: boolean;
  apiRecordTypeValue: string | null | undefined;
  resolveRecordTypeForSearch: (searchRecordType?: string | null) => string;
  contextValues?: Record<string, unknown>;
  enabled?: boolean;
};

export function useParamSpecs({
  siteId,
  recordType,
  searchName,
  selectedSearch,
  isSearchNameAvailable,
  apiRecordTypeValue,
  resolveRecordTypeForSearch,
  contextValues,
  enabled = true,
}: UseParamSpecsArgs) {
  const [paramSpecs, setParamSpecs] = useState<ParamSpec[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isActive = true;
    if (!enabled) {
      setParamSpecs([]);
      setIsLoading(false);
      return;
    }
    const preferredRecordType =
      resolveRecordTypeForSearch(selectedSearch?.recordType) ||
      apiRecordTypeValue ||
      recordType;
    if (!isSearchNameAvailable) {
      setParamSpecs([]);
      return;
    }
    const resolvedRecordType = normalizeRecordType(preferredRecordType);
    if (!searchName || !resolvedRecordType) {
      setParamSpecs([]);
      return;
    }
    const timeout = window.setTimeout(() => {
      setIsLoading(true);
      const trySpecs = (recordTypeToUse: string) =>
        getParamSpecs(
          siteId,
          recordTypeToUse,
          searchName,
          buildContextValues(contextValues || {})
        );

      trySpecs(resolvedRecordType)
        .then((details) => {
          if (!isActive) return;
          setParamSpecs(details || []);
        })
        .catch(() => {
          if (!isActive) return;
          setParamSpecs([]);
        })
        .finally(() => {
          if (!isActive) return;
          setIsLoading(false);
        });
    }, 250);
    return () => {
      isActive = false;
      window.clearTimeout(timeout);
    };
  }, [
    enabled,
    siteId,
    recordType,
    searchName,
    selectedSearch,
    isSearchNameAvailable,
    apiRecordTypeValue,
    resolveRecordTypeForSearch,
    contextValues,
  ]);

  return { paramSpecs, isLoading };
}
