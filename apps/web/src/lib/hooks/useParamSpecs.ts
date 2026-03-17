"use client";

import { useEffect, useMemo, useState } from "react";
import { useDebouncedCallback } from "use-debounce";
import type { ParamSpec, Search } from "@pathfinder/shared";
import { getParamSpecs } from "@/lib/api/sites";
import { normalizeRecordType } from "@/lib/utils/normalizeRecordType";
import { buildContextValues } from "@/lib/utils/buildContextValues";
import type { StepParameters } from "@/lib/strategyGraph/types";

interface AdvancedOptions {
  siteId: string;
  recordType: string | null;
  searchName: string;
  selectedSearch: Search | null;
  isSearchNameAvailable: boolean;
  apiRecordTypeValue: string | null | undefined;
  resolveRecordTypeForSearch: (searchRecordType?: string | null) => string;
  contextValues?: StepParameters;
  enabled?: boolean;
}

type UseParamSpecsResult = { paramSpecs: ParamSpec[]; isLoading: boolean };

/**
 * Consolidated hook for fetching WDK parameter specifications.
 *
 * Simple usage (positional args):
 *   useParamSpecs(siteId, recordType, searchName)
 *
 * Advanced usage (options object — adds debounce, contextValues, record-type
 * resolution, and an enabled guard):
 *   useParamSpecs({ siteId, recordType, searchName, selectedSearch, ... })
 */
export function useParamSpecs(options: AdvancedOptions): UseParamSpecsResult;
export function useParamSpecs(
  siteId: string,
  recordType: string,
  searchName: string,
): UseParamSpecsResult;
export function useParamSpecs(
  siteIdOrOptions: string | AdvancedOptions,
  recordType?: string,
  searchName?: string,
): UseParamSpecsResult {
  const isAdvanced = typeof siteIdOrOptions === "object";

  const advancedResult = useParamSpecsAdvanced(
    isAdvanced
      ? siteIdOrOptions
      : {
          siteId: "",
          recordType: null,
          searchName: "",
          selectedSearch: null,
          isSearchNameAvailable: false,
          apiRecordTypeValue: null,
          resolveRecordTypeForSearch: () => "",
          enabled: false,
        },
  );

  const simpleResult = useParamSpecsSimple(
    isAdvanced ? "" : (siteIdOrOptions as string),
    isAdvanced ? "" : recordType!,
    isAdvanced ? "" : searchName!,
  );

  return isAdvanced ? advancedResult : simpleResult;
}

// ---------------------------------------------------------------------------
// Simple variant (no debounce, no record-type resolution)
// ---------------------------------------------------------------------------

function useParamSpecsSimple(
  siteId: string,
  recordType: string,
  searchName: string,
): UseParamSpecsResult {
  const [paramSpecs, setParamSpecs] = useState<ParamSpec[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!siteId || !recordType || !searchName) return;

    let active = true;

    async function load() {
      setIsLoading(true);
      try {
        const specs = await getParamSpecs(siteId, recordType, searchName);
        if (active) setParamSpecs(specs);
      } catch (err) {
        console.error("[useParamSpecs]", err);
        if (active) setParamSpecs([]);
      } finally {
        if (active) setIsLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [siteId, recordType, searchName]);

  return useMemo(() => ({ paramSpecs, isLoading }), [paramSpecs, isLoading]);
}

// ---------------------------------------------------------------------------
// Advanced variant (debounce, contextValues, record-type resolution)
// ---------------------------------------------------------------------------

function useParamSpecsAdvanced({
  siteId,
  recordType,
  searchName,
  selectedSearch,
  isSearchNameAvailable,
  apiRecordTypeValue,
  resolveRecordTypeForSearch,
  contextValues,
  enabled = true,
}: AdvancedOptions): UseParamSpecsResult {
  const [paramSpecs, setParamSpecs] = useState<ParamSpec[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Stable identity key — only changes when the search itself changes,
  // NOT when contextValues/isSearchNameAvailable flicker during renders.
  const resolvedRecordType = useMemo(() => {
    const preferred =
      resolveRecordTypeForSearch(selectedSearch?.recordType) ||
      apiRecordTypeValue ||
      recordType;
    return normalizeRecordType(preferred);
  }, [recordType, selectedSearch, apiRecordTypeValue, resolveRecordTypeForSearch]);

  const debouncedFetch = useDebouncedCallback((rt: string, ctx: StepParameters) => {
    let isActive = true;
    setIsLoading(true);
    getParamSpecs(siteId, rt, searchName, buildContextValues(ctx || {}))
      .then((details) => {
        if (!isActive) return;
        setParamSpecs(details || []);
      })
      .catch((err) => {
        console.error("[useParamSpecs]", err);
        // Don't clear on error — keep stale specs rather than flashing
        // empty. Params only clear on real identity change.
      })
      .finally(() => {
        if (!isActive) return;
        setIsLoading(false);
      });
    return () => {
      isActive = false;
    };
  }, 250);

  // Primary fetch: fires when search identity changes.
  // contextValues included in deps so the linter is satisfied — the 250ms
  // debounce prevents rapid-fire fetches when the user types.
  useEffect(() => {
    if (!enabled || !searchName || !resolvedRecordType) return;
    debouncedFetch(resolvedRecordType, contextValues || {});
  }, [enabled, siteId, searchName, resolvedRecordType, contextValues, debouncedFetch]);

  return { paramSpecs, isLoading };
}
