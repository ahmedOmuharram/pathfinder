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
  showRaw: boolean;
  rawParams: string;
  paramSpecs: ParamSpec[];
  hiddenDefaults: StepParameters;
  recordTypeValue: string | null | undefined;
  resolveRecordTypeForSearch: (rt?: string | null) => string;
  operatorValue: string;
  colocationParams: Step["colocationParams"];
  onUpdate: (updates: Partial<Step>) => void;
  onClose: () => void;
  setError: (error: string | null) => void;
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
    showRaw,
    rawParams,
    paramSpecs,
    hiddenDefaults,
    resolveRecordTypeForSearch,
    operatorValue,
    colocationParams,
    onUpdate,
    onClose,
    setError,
  } = args;

  return async () => {
    try {
      const nextName = name.trim() || oldName;
      const nextSearchName = searchName || (step.searchName ?? "");
      let parsedParams = parameters;
      if (showRaw) {
        parsedParams = JSON.parse(rawParams) as StepParameters;
      }
      parsedParams = coerceParametersForSpecs(
        parsedParams,
        paramSpecs,
        // Normal save path: do not accept stringified arrays/CSV.
        { allowStringParsing: false },
      );
      // Merge hidden param defaults (lowest priority — user edits win).
      parsedParams = { ...hiddenDefaults, ...parsedParams };
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
            upstream: 1000,
            downstream: 1000,
            strand: "both",
          };
        } else {
          updates.colocationParams = null;
        }
      }
      let validationError: string | null = null;
      if (!isSearchNameAvailable && kind === "search") {
        validationError =
          "Cannot be saved: search name is not available for this record type.";
      }
      if (
        kind === "search" &&
        resolvedRecordType != null &&
        resolvedRecordType !== "" &&
        nextSearchName !== "" &&
        validationError == null
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
            validationError = formatted.message;
          }
        } catch (err) {
          validationError = `Cannot be saved: ${toUserMessage(err, "validation failed.")}`;
        }
      }
      updates.validationError = validationError ?? null;
      onUpdate(updates);
      onClose();
    } catch {
      setError("Invalid JSON in parameters");
    }
  };
}
