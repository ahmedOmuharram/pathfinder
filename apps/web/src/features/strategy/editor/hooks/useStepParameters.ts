"use client";

import { useEffect, useMemo, useState, startTransition } from "react";
import type { Search, StepKind } from "@pathfinder/shared";
import type { StepParameters } from "@/lib/strategyGraph/types";
import { usePrevious } from "@/lib/hooks/usePrevious";
import { useParamSpecs } from "@/lib/hooks/useParamSpecs";
import { extractVocabOptions, type VocabOption } from "@/lib/utils/vocab";
import { extractSpecVocabulary } from "../components/stepEditorUtils";

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
  const [parameters, setParameters] = useState<StepParameters>(initialParameters);
  const [rawParams, setRawParams] = useState(
    JSON.stringify(initialParameters, null, 2),
  );
  const [showRaw, setShowRaw] = useState(false);

  // Dependent parameter state (currently unused placeholders).
  const dependentOptions: Record<string, VocabOption[]> = {};
  const dependentLoading: Record<string, boolean> = {};
  const dependentErrors: Record<string, string | null> = {};

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
      setParameters({});
      setRawParams("{}");
    });
  }, [identityKey, prevIdentityKey]);

  // -------------------------------------------------------------------------
  // Vocabulary options (derived from param specs)
  // -------------------------------------------------------------------------
  const vocabOptions = useMemo(() => {
    return paramSpecs.reduce<Record<string, VocabOption[]>>((acc, spec) => {
      if (!spec.name) return acc;
      const vocabulary = extractSpecVocabulary(spec);
      if (vocabulary) {
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
