/**
 * Step save handler — validation, parameter coercion, API validation
 * call, error formatting, and the final onUpdate/onClose call.
 *
 * Extracted from useStepEditorState so the save workflow (which has
 * its own reason to change: validation rules, coercion logic, API
 * contracts) lives separately from the form state composition.
 */

import type { Step, SearchValidationResponse, ParamSpec } from "@pathfinder/shared";
import type { StepParameters } from "@/lib/strategyGraph/types";
import type { StepKind } from "@pathfinder/shared";
import { validateSearchParams } from "@/lib/api/sites";
import { coerceParametersForSpecs } from "@/features/strategy/parameters/coerce";
import { normalizeRecordType } from "@/lib/utils/normalizeRecordType";
import { formatSearchValidationResponse } from "@/features/strategy/validation/format";
import { toUserMessage } from "@/lib/api/errors";

interface StepSaveHandlerArgs {
  step: Step;
  siteId: string;
  name: string;
  oldName: string;
  searchName: string;
  selectedSearch: { recordType?: string | null } | null;
  isSearchNameAvailable: boolean;
  kind: StepKind;
  parameters: StepParameters;
  paramSpecs: ParamSpec[];
  hiddenDefaults: StepParameters;
  /** Returns the current dirty-field map from RHF formState.dirtyFields.
   *  Called lazily at save time so the value is never stale. When non-empty,
   *  only dirty params (plus hidden defaults) are included in the PATCH payload. */
  getDirtyFields: () => Partial<Record<string, boolean>>;
  recordTypeValue: string | null | undefined;
  resolveRecordTypeForSearch: (rt?: string | null) => string;
  operatorValue: string;
  colocationParams: Step["colocationParams"];
  onUpdate: (updates: Partial<Step>) => void;
  onClose: () => void;
  setError: (error: string | null) => void;
  /** Set a field-level error from WDK validation `byKey` entries. Backed by
   *  `form.setError()` in the caller. */
  setFieldError: (name: string, error: { type: string; message: string }) => void;
}

/**
 * Build a save handler function from the current editor state.
 *
 * This is a plain function factory (not a hook) so it can be tested
 * without React rendering. The caller (useStepEditorState) wraps it
 * in the appropriate memoization.
 */
export function buildStepSaveHandler(args: StepSaveHandlerArgs): () => Promise<void> {
  const {
    step,
    siteId,
    name,
    oldName,
    searchName,
    selectedSearch,
    isSearchNameAvailable,
    kind,
    parameters,
    paramSpecs,
    hiddenDefaults,
    getDirtyFields,
    resolveRecordTypeForSearch,
    operatorValue,
    colocationParams,
    onUpdate,
    onClose,
    setError,
    setFieldError,
  } = args;

  return async () => {
    try {
      const nextName = name.trim() || oldName;
      const nextSearchName = searchName || (step.searchName ?? "");
      const coercedParams = coerceParametersForSpecs(
        parameters,
        paramSpecs,
        // Normal save path: do not accept stringified arrays/CSV.
        { allowStringParsing: false },
      );

      // Gap 3: Serialize multi-pick arrays to JSON strings for WDK.
      const serializedParams = serializeMultiPickValues(coercedParams);

      // Gap 1: When dirtyFields has entries, only include params the user
      // actually changed. Hidden defaults are always included (they are
      // invisible to the user and required by WDK).
      const dirtyFields = getDirtyFields();
      const hasDirtyEntries = Object.keys(dirtyFields).some((k) => dirtyFields[k] === true);
      const filteredParams = hasDirtyEntries
        ? filterToDirtyParams(serializedParams, dirtyFields)
        : serializedParams;

      // Merge hidden param defaults (lowest priority — user edits win).
      const parsedParams = { ...hiddenDefaults, ...filteredParams };
      // Do not enforce business-required checks here (backend is authoritative).
      const updates: Partial<Step> = {
        displayName: nextName,
        parameters: parsedParams,
      };
      const selectedRecordType = resolveRecordTypeForSearch(selectedSearch?.recordType);
      const resolvedRecordType = normalizeRecordType(selectedRecordType);
      if (selectedRecordType) {
        updates.recordType = selectedRecordType;
      }
      if (kind !== "combine") {
        updates.searchName = nextSearchName;
      }
      if (kind === "combine") {
        const nextOperator = operatorValue || (step.operator ?? null);
        if (nextOperator == null || nextOperator === "") {
          setError("Combine steps require an operator to be selected.");
          return;
        }
        updates.operator = nextOperator;
        if (nextOperator === "COLOCATE") {
          updates.colocationParams = colocationParams ?? {
            operation: "overlaps",
            strand: "either strand",
            output: "a",
            regionA: "exact",
            beginA: "start",
            beginDirectionA: "+",
            beginOffsetA: 0,
            endA: "stop",
            endDirectionA: "+",
            endOffsetA: 0,
            regionB: "exact",
            beginB: "start",
            beginDirectionB: "+",
            beginOffsetB: 0,
            endB: "stop",
            endDirectionB: "+",
            endOffsetB: 0,
          };
        } else {
          updates.colocationParams = null;
        }
      }
      let validationMessage: string | null = null;
      if (!isSearchNameAvailable && kind === "search") {
        validationMessage =
          "Cannot be saved: search name is not available for this record type.";
      }
      if (
        kind === "search" &&
        resolvedRecordType != null &&
        resolvedRecordType !== "" &&
        nextSearchName !== "" &&
        validationMessage == null
      ) {
        try {
          const response: SearchValidationResponse = await validateSearchParams(
            siteId,
            resolvedRecordType,
            nextSearchName,
            parsedParams,
          );
          const formatted = formatSearchValidationResponse(response);
          if (formatted.message != null && formatted.message !== "") {
            validationMessage = formatted.message;
          }
          // Gap 2: Map WDK field-level validation errors to form field errors.
          const byKey = response.validation.errors?.byKey;
          if (byKey != null) {
            for (const [fieldName, messages] of Object.entries(byKey)) {
              if (!Array.isArray(messages) || messages.length === 0) continue;
              setFieldError(fieldName, { type: "server", message: messages[0]! });
            }
          }
        } catch (err) {
          validationMessage = `Cannot be saved: ${toUserMessage(err, "validation failed.")}`;
        }
      }
      updates.validation =
        validationMessage != null
          ? {
              level: "UNRUNNABLE",
              isValid: false,
              errors: { general: [validationMessage], byKey: {} },
            }
          : null;
      onUpdate(updates);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save step");
    }
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Keep only parameters whose key is marked dirty in RHF's dirtyFields map. */
function filterToDirtyParams(
  params: StepParameters,
  dirtyFields: Partial<Record<string, boolean>>,
): StepParameters {
  const filtered: StepParameters = {};
  for (const key of Object.keys(params)) {
    if (dirtyFields[key] === true) {
      filtered[key] = params[key];
    }
  }
  return filtered;
}

/**
 * Serialize multi-pick array values to JSON strings for WDK.
 *
 * WDK expects multi-pick parameter values as JSON-encoded string arrays
 * (e.g. `'["GO:0006915","GO:0006916"]'`). After coercion, multi-pick
 * values are `string[]`. This converts them to their JSON string form.
 */
function serializeMultiPickValues(params: StepParameters): StepParameters {
  const result: StepParameters = {};
  for (const [key, value] of Object.entries(params)) {
    result[key] = Array.isArray(value) ? JSON.stringify(value) : value;
  }
  return result;
}
