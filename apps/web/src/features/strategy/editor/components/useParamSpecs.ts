"use client";

import { useEffect, useState } from "react";
import type { ParamSpec, Search } from "@pathfinder/shared";
import { getParamSpecs } from "@/lib/api/client";
import { normalizeRecordType, toApiRecordType } from "@/features/strategy/recordType";

type UseParamSpecsArgs = {
  siteId: string;
  recordType: string | null;
  searchName: string;
  selectedSearch: Search | null;
  isSearchNameAvailable: boolean;
  apiRecordTypeValue: string | null | undefined;
  resolveRecordTypeForSearch: (searchRecordType?: string | null) => string;
};

export function useParamSpecs({
  siteId,
  recordType,
  searchName,
  selectedSearch,
  isSearchNameAvailable,
  apiRecordTypeValue,
  resolveRecordTypeForSearch,
}: UseParamSpecsArgs) {
  const [paramSpecs, setParamSpecs] = useState<ParamSpec[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isActive = true;
    const preferredRecordType =
      resolveRecordTypeForSearch(selectedSearch?.recordType) ||
      apiRecordTypeValue ||
      recordType;
    if (!isSearchNameAvailable) {
      setParamSpecs([]);
      return;
    }
    const resolvedRecordType = toApiRecordType(preferredRecordType);
    const fallbackRecordType = normalizeRecordType(preferredRecordType);
    if (!searchName || !resolvedRecordType) {
      setParamSpecs([]);
      return;
    }
    const timeout = window.setTimeout(() => {
      setIsLoading(true);
      const trySpecs = (recordTypeToUse: string) =>
        getParamSpecs(siteId, recordTypeToUse, searchName);

      trySpecs(resolvedRecordType)
        .then((details) => {
          if (!isActive) return;
          setParamSpecs(details || []);
        })
        .catch(() => {
          if (!isActive) return;
          const fallbackTypes: string[] = [];
          if (fallbackRecordType && fallbackRecordType !== resolvedRecordType) {
            fallbackTypes.push(fallbackRecordType);
          }
          const next = fallbackTypes.shift();
          if (!next) {
            setParamSpecs([]);
            return;
          }

          trySpecs(next)
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
    siteId,
    recordType,
    searchName,
    selectedSearch,
    isSearchNameAvailable,
    apiRecordTypeValue,
    resolveRecordTypeForSearch,
  ]);

  return { paramSpecs, isLoading };
}
