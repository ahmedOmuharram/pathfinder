"use client";

import { useState } from "react";
import { useDebounce } from "use-debounce";
import { useFormContext, useWatch, type Control, type FieldPath, type FieldValues } from "react-hook-form";
import { useQueries, keepPreviousData } from "@tanstack/react-query";
import type { ParamSpec } from "@pathfinder/shared";
import { extractVocabOptions, type VocabOption } from "@/lib/utils/vocab";
import { extractSpecVocabulary } from "../components/stepEditorUtils";
import { refreshDependentParams } from "@/lib/api/sites";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UseDependentParamsArgs<T extends FieldValues = FieldValues> {
  /** RHF control object from useForm / useParamForm. */
  control: Control<T>;
  /** All param specs for this search. */
  specs: ParamSpec[];
  /** Site identifier (e.g. "plasmodb"). */
  siteId: string;
  /** Normalized record type (e.g. "transcript"). */
  recordType: string;
  /** WDK search name (e.g. "GenesByTaxon"). */
  searchName: string;
}

interface UseDependentParamsResult {
  /** Refreshed vocabulary options keyed by downstream param name. */
  dependentOptions: Record<string, VocabOption[]>;
  /** Loading state keyed by downstream param name. */
  dependentLoading: Record<string, boolean>;
  /** Error messages keyed by downstream param name, null when no error. */
  dependentErrors: Record<string, string | null>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------


// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Watches upstream parameters (those with non-empty `dependentParams`) via
 * RHF's `useWatch`, and calls the WDK refreshed-dependent-params endpoint
 * when their values change.
 *
 * Returns refreshed vocabulary options, loading flags, and error messages
 * keyed by downstream (dependent) param name.
 *
 * Uses TanStack Query with debounced inputs for automatic staleness
 * management, caching, and deduplication.
 */
export function useDependentParams<T extends FieldValues = FieldValues>({
  control,
  specs,
  siteId,
  recordType,
  searchName,
}: UseDependentParamsArgs<T>): UseDependentParamsResult {
  // Build the set of upstream param specs (those with dependentParams).
  const upstreamSpecs = specs.filter(
    (s) =>
      s.name !== "" &&
      s.dependentParams != null &&
      s.dependentParams.length > 0,
  );

  const upstreamNames = upstreamSpecs.map((s) => s.name);

  // Watch all upstream param values via RHF.
  // useWatch requires FieldPath<T>[] but our param names are dynamic strings
  // from WDK specs. The cast is safe because RHF's runtime doesn't validate
  // field paths — it simply subscribes to the named fields.
  const rawWatched = useWatch({
    control,
    name: upstreamNames as FieldPath<T>[],
  });
  // Serialize watched values for stable comparison.
  const watchedSerialized = (() => {
    const values = Array.isArray(rawWatched) ? (rawWatched as unknown[]) : [rawWatched as unknown];
    return values.map((v) => JSON.stringify(v));
  })();

  // Debounce the serialized values so TQ queries don't fire on every keystroke.
  const [debouncedSerialized] = useDebounce(watchedSerialized, 250);

  // Capture initial values once to prevent firing on mount.
  const [initialSerialized] = useState(() => watchedSerialized);

  const { getValues } = useFormContext();

  // One query per upstream param. The query fires when that param's debounced
  // value diverges from its initial mount-time value.
  const queryResults = useQueries({
    queries: upstreamSpecs.map((spec, idx) => {
      const paramName = spec.name;
      const debouncedValue = debouncedSerialized[idx] ?? "";
      const initialValue = initialSerialized[idx] ?? "";
      const hasChanged = debouncedValue !== initialValue;

      return {
        queryKey: [
          "dependent-params",
          siteId,
          recordType,
          searchName,
          paramName,
          debouncedValue,
        ] as const,
        queryFn: () => {
          const contextValues: Record<string, unknown> = { ...getValues() };
          return refreshDependentParams(
            siteId,
            recordType,
            searchName,
            paramName,
            contextValues,
          );
        },
        enabled: hasChanged,
        placeholderData: keepPreviousData,
        staleTime: 0,
        gcTime: 30_000,
      };
    }),
  });

  // Aggregate results from all queries into the unified return shape.
  const dependentOptions: Record<string, VocabOption[]> = {};
  const dependentLoading: Record<string, boolean> = {};
  const dependentErrors: Record<string, string | null> = {};

  for (let i = 0; i < upstreamSpecs.length; i++) {
    const spec = upstreamSpecs[i]!;
    const depParams = spec.dependentParams ?? [];
    const result = queryResults[i];
    if (result == null) continue;

    const isLoading = result.isFetching;
    const errorMsg =
      result.error instanceof Error ? result.error.message : null;

    // Set loading/error state for each downstream param.
    for (const dep of depParams) {
      dependentLoading[dep] = isLoading;
      dependentErrors[dep] = errorMsg;
    }

    // Extract vocabulary options from the returned specs.
    if (result.data != null) {
      for (const refreshedSpec of result.data) {
        if (!refreshedSpec.name) continue;
        const vocab = extractSpecVocabulary(refreshedSpec);
        if (vocab != null) {
          dependentOptions[refreshedSpec.name] = extractVocabOptions(vocab);
        }
      }
    }
  }

  return { dependentOptions, dependentLoading, dependentErrors };
}
