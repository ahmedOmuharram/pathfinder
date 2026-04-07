"use client";

import { useCallback, useEffect, useMemo, useRef, useState, startTransition } from "react";
import { useFormContext, useWatch, type Control, type FieldPath, type FieldValues } from "react-hook-form";
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
 * Debounces rapid changes (250ms) and ignores stale responses using a
 * monotonically incrementing counter.
 */
export function useDependentParams<T extends FieldValues = FieldValues>({
  control,
  specs,
  siteId,
  recordType,
  searchName,
}: UseDependentParamsArgs<T>): UseDependentParamsResult {
  const [dependentOptions, setDependentOptions] = useState<Record<string, VocabOption[]>>(
    {},
  );
  const [dependentLoading, setDependentLoading] = useState<Record<string, boolean>>({});
  const [dependentErrors, setDependentErrors] = useState<Record<string, string | null>>(
    {},
  );

  // Build the set of upstream param names (those with dependentParams).
  const upstreamSpecs = useMemo(
    () =>
      specs.filter(
        (s) =>
          s.name !== "" &&
          s.dependentParams != null &&
          s.dependentParams.length > 0,
      ),
    [specs],
  );

  const upstreamNames = useMemo(
    () => upstreamSpecs.map((s) => s.name),
    [upstreamSpecs],
  );

  // Watch all upstream param values via RHF.
  // When no upstream params exist, useWatch receives an empty array and
  // returns an empty array — no subscriptions, no re-renders.
  //
  // RHF returns the values typed against the dynamic FieldValues generic.
  // Since we pass a string[] (not a const tuple), the inferred element type
  // is wide. We normalize to unknown[] for safe comparison below.
  // useWatch requires FieldPath<T>[] but our param names are dynamic strings
  // from WDK specs. The cast is safe because RHF's runtime doesn't validate
  // field paths — it simply subscribes to the named fields.
  const rawWatched = useWatch({
    control,
    name: upstreamNames as FieldPath<T>[],
  });
  const watchedValues = Array.isArray(rawWatched) ? (rawWatched as unknown[]) : [rawWatched as unknown];

  // Stale-response guard: monotonically incrementing counter.
  const refreshCounterRef = useRef(0);

  // Debounce timer ref for cleanup.
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Track previous watched values to detect actual changes and identify
  // which specific upstream param changed. Initialized to `null` so the
  // first render seeds the ref without triggering a refresh.
  const prevWatchedRef = useRef<unknown[] | null>(null);

  const { getValues } = useFormContext();

  const doRefresh = useCallback(
    (changedParamName: string, depParams: string[]) => {
      const counter = ++refreshCounterRef.current;

      // Set loading state for dependent params.
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

      // Get ALL current form values for the context.
      const contextValues: Record<string, unknown> = { ...getValues() };

      refreshDependentParams(siteId, recordType, searchName, changedParamName, contextValues)
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
    [getValues, siteId, recordType, searchName],
  );

  // Effect: compare watched values to previous, find the changed upstream
  // param, and trigger a debounced refresh.
  useEffect(() => {
    if (upstreamSpecs.length === 0) return;

    // First render: seed the ref with initial values and skip refresh.
    if (prevWatchedRef.current === null) {
      prevWatchedRef.current = watchedValues.slice();
      return;
    }

    const prev = prevWatchedRef.current;

    // Find which upstream param changed.
    let changedIdx = -1;
    for (let i = 0; i < upstreamSpecs.length; i++) {
      const prevStr = JSON.stringify(prev[i]);
      const currStr = JSON.stringify(watchedValues[i]);
      if (prevStr !== currStr) {
        changedIdx = i;
        break;
      }
    }

    prevWatchedRef.current = watchedValues.slice();

    if (changedIdx === -1) return;

    const changedSpec = upstreamSpecs[changedIdx]!;
    const changedParamName = changedSpec.name;
    const depParams = changedSpec.dependentParams ?? [];
    if (depParams.length === 0) return;

    // Debounce: clear any pending timer and schedule a new one.
    if (debounceTimerRef.current != null) {
      clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = setTimeout(() => {
      doRefresh(changedParamName, depParams);
    }, 250);
  }, [watchedValues, upstreamSpecs, doRefresh]);

  // Cleanup debounce timer on unmount.
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current != null) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  return useMemo(
    () => ({ dependentOptions, dependentLoading, dependentErrors }),
    [dependentOptions, dependentLoading, dependentErrors],
  );
}
