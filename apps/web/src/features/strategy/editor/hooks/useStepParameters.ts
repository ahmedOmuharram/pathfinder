"use client";

import { useRef, useState, startTransition } from "react";
import type { ParamSpec, Search, StepKind } from "@pathfinder/shared";
import type { StepParameters } from "@/lib/strategyGraph/types";
import { useParamSpecs } from "@/lib/hooks/useParamSpecs";
import { extractVocabOptions, type VocabOption } from "@/lib/utils/vocab";
import { extractSpecVocabulary } from "../components/stepEditorUtils";
import { refreshDependentParams } from "@/lib/api/sites";
import { normalizeRecordType } from "@/lib/utils/normalizeRecordType";

interface UseStepParametersArgs {
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

  const triggerDependentRefresh = (prevParams: StepParameters, nextParams: StepParameters) => {
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
  };

  const setParameters = (action: StepParameters | ((prev: StepParameters) => StepParameters)) => {
    setParametersRaw((prev) => {
      const next = typeof action === "function" ? action(prev) : action;
      // Trigger dependent param refresh if a param with dependentParams changed.
      // Uses queueMicrotask so state is committed before the refresh runs.
      queueMicrotask(() => triggerDependentRefresh(prev, next));
      return next;
    });
  };


  // -------------------------------------------------------------------------
  // Vocabulary options (derived from param specs)
  // -------------------------------------------------------------------------
  const vocabOptions = paramSpecs.reduce<Record<string, VocabOption[]>>((acc, spec) => {
    if (spec.name === "") return acc;
    const vocabulary = extractSpecVocabulary(spec);
    if (vocabulary != null) {
      acc[spec.name] = extractVocabOptions(vocabulary);
    }
    return acc;
  }, {});

  // -------------------------------------------------------------------------
  // Hidden param defaults — for params with isVisible=false that no composite
  // widget claims. These get merged into the save payload at lowest priority.
  // -------------------------------------------------------------------------
  const hiddenDefaults: StepParameters = {};
  for (const spec of paramSpecs) {
    if (spec.isVisible === false && spec.name) {
      const defaultVal = spec.initialDisplayValue;
      if (defaultVal != null) {
        hiddenDefaults[spec.name] = defaultVal;
      } else if (spec.type === "input-step") {
        hiddenDefaults[spec.name] = "";
      }
    }
  }

  return {
    parameters,
    setParameters,
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
