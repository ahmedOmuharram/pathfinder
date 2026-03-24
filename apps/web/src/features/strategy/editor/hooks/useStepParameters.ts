"use client";

import { useCallback, useEffect, useMemo, useRef, useState, startTransition } from "react";
import type { ParamSpec, Search, StepKind } from "@pathfinder/shared";
import type { StepParameters } from "@/lib/strategyGraph/types";
import { usePrevious } from "@/lib/hooks/usePrevious";
import { useParamSpecs } from "@/lib/hooks/useParamSpecs";
import { extractVocabOptions, type VocabOption } from "@/lib/utils/vocab";
import { extractSpecVocabulary } from "../components/stepEditorUtils";
import { coerceParametersForSpecs } from "@/features/strategy/parameters/coerce";
import { refreshDependentParams } from "@/lib/api/sites";
import { normalizeRecordType } from "@/lib/utils/normalizeRecordType";

interface UseStepParametersArgs {
  stepId: string;
  siteId: string;
  recordType: string | null;
  kind: StepKind;
  searchName: string;
  selectedSearch: Search | null;
  isSearchNameAvailable: boolean;
  apiRecordTypeValue: string | null | undefined;
  resolveRecordTypeForSearch: (searchRecordType?: string | null) => string;
  initialParameters: StepParameters;
}

export function useStepParameters({
  stepId,
  siteId,
  recordType,
  kind,
  searchName,
  selectedSearch,
  isSearchNameAvailable,
  apiRecordTypeValue,
  resolveRecordTypeForSearch,
  initialParameters,
}: UseStepParametersArgs) {
  const [parameters, setParametersRaw] = useState<StepParameters>(initialParameters);
  const [rawParams, setRawParams] = useState(
    JSON.stringify(initialParameters, null, 2),
  );
  const [showRaw, setShowRaw] = useState(false);

  // Dependent parameter state
  const [dependentOptions, setDependentOptions] = useState<Record<string, VocabOption[]>>({});
  const [dependentLoading, setDependentLoading] = useState<Record<string, boolean>>({});
  const [dependentErrors, setDependentErrors] = useState<Record<string, string | null>>({});

  // -------------------------------------------------------------------------
  // Param specs
  // -------------------------------------------------------------------------
  const { paramSpecs, isLoading } = useParamSpecs({
    siteId,
    recordType,
    searchName,
    selectedSearch,
    isSearchNameAvailable,
    apiRecordTypeValue,
    resolveRecordTypeForSearch,
    contextValues: parameters,
    enabled: kind !== "combine",
  });

  // -------------------------------------------------------------------------
  // Dependent parameter refresh — triggered by setParameters wrapper
  // -------------------------------------------------------------------------
  const refreshCounterRef = useRef(0);

  const triggerDependentRefresh = useCallback(
    (prevParams: StepParameters, nextParams: StepParameters) => {
      if (paramSpecs.length === 0) return;
      if (kind === "combine") return;

      const changedParamName = findChangedParam(prevParams, nextParams, paramSpecs);
      if (changedParamName == null) return;

      const changedSpec = paramSpecs.find((s) => s.name === changedParamName);
      const depParams = changedSpec?.dependentParams;
      if (depParams == null || depParams.length === 0) return;

      const counter = ++refreshCounterRef.current;

      // Set loading state for dependent params
      setDependentLoading((prev) => {
        const next = { ...prev };
        for (const dep of depParams) next[dep] = true;
        return next;
      });
      setDependentErrors((prev) => {
        const next = { ...prev };
        for (const dep of depParams) next[dep] = null;
        return next;
      });

      // Resolve record type for the API call
      const resolved = resolveRecordTypeForSearch(selectedSearch?.recordType);
      const preferred =
        (resolved !== "" ? resolved : null) ?? apiRecordTypeValue ?? recordType;
      const normalizedRT = normalizeRecordType(preferred) ?? "";

      refreshDependentParams(
        siteId,
        normalizedRT,
        searchName,
        changedParamName,
        nextParams,
      )
        .then((refreshedSpecs) => {
          if (refreshCounterRef.current !== counter) return; // stale
          startTransition(() => {
            setDependentOptions((prev) => {
              const next = { ...prev };
              for (const spec of refreshedSpecs) {
                if (!spec.name) continue;
                const vocab = extractSpecVocabulary(spec);
                if (vocab != null) {
                  next[spec.name] = extractVocabOptions(vocab);
                }
              }
              return next;
            });
            setDependentLoading((prev) => {
              const next = { ...prev };
              for (const dep of depParams) next[dep] = false;
              return next;
            });
          });
        })
        .catch((err: unknown) => {
          if (refreshCounterRef.current !== counter) return;
          const msg = err instanceof Error ? err.message : String(err);
          setDependentErrors((prev) => {
            const next = { ...prev };
            for (const dep of depParams) next[dep] = msg;
            return next;
          });
          setDependentLoading((prev) => {
            const next = { ...prev };
            for (const dep of depParams) next[dep] = false;
            return next;
          });
        });
    },
    [paramSpecs, kind, siteId, searchName, recordType, selectedSearch, apiRecordTypeValue, resolveRecordTypeForSearch],
  );

  const setParameters = useCallback(
    (action: StepParameters | ((prev: StepParameters) => StepParameters)) => {
      setParametersRaw((prev) => {
        const next = typeof action === "function" ? action(prev) : action;
        // Trigger dependent param refresh if a param with dependentParams changed.
        // Uses queueMicrotask so state is committed before the refresh runs.
        queueMicrotask(() => triggerDependentRefresh(prev, next));
        return next;
      });
    },
    [triggerDependentRefresh],
  );

  // -------------------------------------------------------------------------
  // Reset params when step identity or search name changes (user switched search).
  // Keyed only on stepId + searchName — NOT record type, which can resolve
  // asynchronously and cause a spurious reset that clears loaded params.
  // -------------------------------------------------------------------------
  const identityKey = `${stepId}:${searchName || ""}`;
  const prevIdentityKey = usePrevious(identityKey);

  useEffect(() => {
    if (prevIdentityKey === undefined) return;
    if (prevIdentityKey === identityKey) return;
    startTransition(() => {
      setParametersRaw({});
      setRawParams("{}");
    });
  }, [identityKey, prevIdentityKey]);

  // -------------------------------------------------------------------------
  // Coerce initial params when paramSpecs first load.
  // WDK-synced strategies store multi-pick values as JSON-encoded strings
  // (e.g. '["Plasmodium falciparum 3D7"]'). The widgets expect arrays, so
  // we coerce once paramSpecs are available to determine which params are
  // multi-pick. This runs exactly once per mount (component remounts for
  // each new step since StepEditor is conditionally rendered).
  // -------------------------------------------------------------------------
  const hasCoercedRef = useRef(false);
  useEffect(() => {
    if (paramSpecs.length === 0 || isLoading) return;
    if (hasCoercedRef.current) return;
    hasCoercedRef.current = true;

    startTransition(() => {
      setParametersRaw((prev) => {
        if (Object.keys(prev).length === 0) return prev;
        return coerceParametersForSpecs(prev, paramSpecs, {
          allowStringParsing: false,
        });
      });
      setRawParams((prev) => {
        try {
          const obj = JSON.parse(prev) as StepParameters;
          if (Object.keys(obj).length === 0) return prev;
          const coerced = coerceParametersForSpecs(obj, paramSpecs, {
            allowStringParsing: false,
          });
          return JSON.stringify(coerced, null, 2);
        } catch {
          return prev;
        }
      });
    });
  }, [paramSpecs, isLoading]);

  // -------------------------------------------------------------------------
  // Vocabulary options (derived from param specs)
  // -------------------------------------------------------------------------
  const vocabOptions = useMemo(() => {
    return paramSpecs.reduce<Record<string, VocabOption[]>>((acc, spec) => {
      if (spec.name === "") return acc;
      const vocabulary = extractSpecVocabulary(spec);
      if (vocabulary != null) {
        acc[spec.name] = extractVocabOptions(vocabulary);
      }
      return acc;
    }, {});
  }, [paramSpecs]);

  // -------------------------------------------------------------------------
  // Hidden param defaults — for params with isVisible=false that no composite
  // widget claims. These get merged into the save payload at lowest priority.
  // -------------------------------------------------------------------------
  const hiddenDefaults = useMemo(() => {
    const defaults: StepParameters = {};
    for (const spec of paramSpecs) {
      if (spec.isVisible === false && spec.name) {
        const defaultVal = spec.initialDisplayValue;
        if (defaultVal != null) {
          defaults[spec.name] = defaultVal;
        } else if (spec.type === "input-step") {
          defaults[spec.name] = "";
        }
      }
    }
    return defaults;
  }, [paramSpecs]);

  return {
    parameters,
    setParameters,
    rawParams,
    setRawParams,
    showRaw,
    setShowRaw,
    paramSpecs,
    isLoading,
    vocabOptions,
    hiddenDefaults,
    dependentOptions,
    dependentLoading,
    dependentErrors,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Find the first parameter that changed between the previous and current
 * values, among only those params that have `dependentParams` in the specs.
 */
function findChangedParam(
  prev: StepParameters,
  curr: StepParameters,
  specs: ParamSpec[],
): string | null {
  const specsWithDeps = new Set(
    specs
      .filter((s) => s.dependentParams != null && s.dependentParams.length > 0)
      .map((s) => s.name),
  );
  for (const key of Object.keys(curr)) {
    if (!specsWithDeps.has(key)) continue;
    if (JSON.stringify(prev[key]) !== JSON.stringify(curr[key])) return key;
  }
  return null;
}
