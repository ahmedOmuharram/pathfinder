"use client";

import { useCallback, useEffect, useMemo, useState, startTransition } from "react";
import { usePrevious } from "@/lib/hooks/usePrevious";
import type { RecordType, Search, SearchValidationResponse } from "@pathfinder/shared";
import { getRecordTypes, getSearches, validateSearchParams } from "@/lib/api/client";
import type { StrategyStep } from "@/features/strategy/types";
import { StepCombineOperatorSelect } from "./components/StepCombineOperatorSelect";
import { StepEditorFooter } from "./components/StepEditorFooter";
import { StepEditorHeader } from "./components/StepEditorHeader";
import { StepNameFields } from "./components/StepNameFields";
import { StepParamFields } from "./components/StepParamFields";
import { StepRawParamsEditor } from "./components/StepRawParamsEditor";
import { StepSearchSelector } from "./components/StepSearchSelector";
import { useParamSpecs } from "./components/useParamSpecs";
import {
  extractSpecVocabulary,
  extractVocabOptions,
  type VocabOption,
} from "./components/stepEditorUtils";
import { Modal } from "@/lib/components/Modal";
import { coerceParametersForSpecs } from "@/features/strategy/parameters/coerce";
import { normalizeRecordType } from "@/features/strategy/recordType";
import { formatSearchValidationResponse } from "@/features/strategy/validation/format";
import { toUserMessage } from "@/lib/api/errors";
import { inferStepKind } from "@/lib/strategyGraph";

interface StepEditorProps {
  step: StrategyStep;
  siteId: string;
  recordType: string | null;
  strategyId: string | null;
  onUpdate: (updates: Partial<StrategyStep>) => void;
  onClose: () => void;
}

export function StepEditor({
  step,
  siteId,
  recordType,
  onUpdate,
  onClose,
}: StepEditorProps) {
  const [oldName, setOldName] = useState(step.displayName);
  const [name, setName] = useState(step.displayName);
  const [editableSearchName, setEditableSearchName] = useState(step.searchName || "");
  const [operatorValue, setOperatorValue] = useState(step.operator || "");
  const [colocationParams, setColocationParams] = useState(step.colocationParams);
  const [recordTypeValue, setRecordTypeValue] = useState(
    normalizeRecordType(step.recordType || recordType),
  );
  const [parameters, setParameters] = useState<Record<string, unknown>>(
    step.parameters || {},
  );
  const [recordTypeOptions, setRecordTypeOptions] = useState<RecordType[]>([]);
  const [recordTypeFilter, setRecordTypeFilter] = useState("");
  const [searchOptions, setSearchOptions] = useState<Search[]>([]);
  const [isLoadingSearches, setIsLoadingSearches] = useState(false);
  const [searchListError, setSearchListError] = useState<string | null>(null);
  const dependentOptions: Record<string, VocabOption[]> = {};
  const dependentLoading: Record<string, boolean> = {};
  const dependentErrors: Record<string, string | null> = {};
  const prevStepId = usePrevious(step.id);
  const [rawParams, setRawParams] = useState(
    JSON.stringify(step.parameters || {}, null, 2),
  );
  const [showRaw, setShowRaw] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const searchName = editableSearchName.trim();
  const kind = inferStepKind(step);
  const normalizedRecordTypeValue = normalizeRecordType(recordTypeValue);
  const apiRecordTypeValue = normalizedRecordTypeValue;
  const stepValidationError = step.validationError;
  const selectedSearch = useMemo(() => {
    if (!searchName) return null;
    return searchOptions.find((option) => option.name === searchName) || null;
  }, [searchName, searchOptions]);
  const isSearchNameAvailable = useMemo(
    () =>
      searchName ? searchOptions.some((option) => option.name === searchName) : true,
    [searchName, searchOptions],
  );
  const filteredSearchOptions = useMemo(() => {
    const query = editableSearchName.trim().toLowerCase();
    if (!query) return searchOptions;
    return searchOptions.filter((option) => {
      const label = (option.displayName || option.name).toLowerCase();
      return label.includes(query) || option.name.toLowerCase().includes(query);
    });
  }, [editableSearchName, searchOptions]);

  const filteredRecordTypes = useMemo(() => {
    const query = recordTypeFilter.trim().toLowerCase();
    if (!query) return recordTypeOptions;
    return recordTypeOptions.filter((option) => {
      const label = (option.displayName || option.name).toLowerCase();
      return label.includes(query) || option.name.toLowerCase().includes(query);
    });
  }, [recordTypeFilter, recordTypeOptions]);

  useEffect(() => {
    let isActive = true;
    getRecordTypes(siteId)
      .then((results) => {
        if (!isActive) return;
        const options = (results || [])
          .filter((item): item is RecordType => Boolean(item && item.name))
          .sort((a, b) =>
            (a.displayName || a.name).localeCompare(b.displayName || b.name),
          );
        setRecordTypeOptions(options);
      })
      .catch(() => {
        if (!isActive) return;
        setRecordTypeOptions([]);
      });
    return () => {
      isActive = false;
    };
  }, [siteId]);

  useEffect(() => {
    if (recordTypeOptions.length === 0) return;
    if (!recordTypeValue) return;
    const normalized = normalizeRecordType(recordTypeValue);
    const exists = recordTypeOptions.some((option) => option.name === normalized);
    if (!exists) {
      startTransition(() => {
        setRecordTypeValue("");
      });
    }
  }, [recordTypeOptions, recordTypeValue]);

  const resolveRecordTypeForSearch = useCallback(
    (searchRecordType?: string | null) => {
      const normalized = normalizeRecordType(searchRecordType || "");
      if (normalized) {
        const exists = recordTypeOptions.some((option) => option.name === normalized);
        if (exists) return normalized;
      }
      return normalizeRecordType(recordTypeValue || recordType) || "";
    },
    [recordType, recordTypeOptions, recordTypeValue],
  );

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

  const validationErrorKeys = useMemo(() => {
    if (!stepValidationError) return new Set<string>();
    const keys = new Set<string>();
    const paramNames = new Set(
      paramSpecs.map((spec) => spec.name).filter(Boolean) as string[],
    );
    stepValidationError
      .replace(/^Cannot be saved:\s*/i, "")
      .split(";")
      .map((part) => part.trim())
      .forEach((part) => {
        if (!part) return;
        const splitIndex = part.indexOf(":");
        if (splitIndex === -1) return;
        const key = part.slice(0, splitIndex).trim();
        if (paramNames.has(key)) {
          keys.add(key);
        }
      });
    return keys;
  }, [stepValidationError, paramSpecs]);

  useEffect(() => {
    let isActive = true;
    const resolvedRecordType = resolveRecordTypeForSearch();
    const normalizedRecordType = normalizeRecordType(resolvedRecordType || recordType);
    if (!normalizedRecordType) {
      startTransition(() => {
        setSearchOptions([]);
        setSearchListError(null);
      });
      return;
    }
    startTransition(() => {
      setIsLoadingSearches(true);
      setSearchListError(null);
    });
    getSearches(siteId, normalizedRecordType)
      .then((results) => {
        if (!isActive) return;
        const options = (results || [])
          .filter((item): item is Search => Boolean(item && item.name))
          .sort((a, b) =>
            (a.displayName || a.name).localeCompare(b.displayName || b.name),
          );
        setSearchOptions(options);
        if (options.length === 0) {
          setSearchListError("No searches available for this record type.");
        }
      })
      .catch(() => {
        if (!isActive) return;
        setSearchOptions([]);
        setSearchListError("Failed to load search list.");
      })
      .finally(() => {
        if (!isActive) return;
        setIsLoadingSearches(false);
      });
    return () => {
      isActive = false;
    };
  }, [siteId, recordType, resolveRecordTypeForSearch]);

  const resolvedSpecRecordType = resolveRecordTypeForSearch(selectedSearch?.recordType);
  const specKey = `${step.id}:${resolvedSpecRecordType || ""}:${searchName || ""}`;
  const prevSpecKey = usePrevious(specKey);

  useEffect(() => {
    if (prevSpecKey === undefined) return;
    if (prevSpecKey === specKey) return;
    startTransition(() => {
      setParameters({});
      setRawParams("{}");
    });
  }, [specKey, prevSpecKey]);

  useEffect(() => {
    const isNewStep = prevStepId !== step.id;
    if (!isNewStep) return;

    const nextParams = coerceParametersForSpecs(
      (step.parameters || {}) as Record<string, unknown>,
      paramSpecs,
      // Normal UI flow: do not accept/parse stringified arrays or CSV.
      { allowStringParsing: false },
    );
    const nextOldName = step.displayName;
    const nextName = nextOldName;
    const nextSearchName = step.searchName || "";
    const nextRecordType = normalizeRecordType(step.recordType || recordType);
    const nextRawParams = JSON.stringify(nextParams, null, 2);
    // Batch state updates to avoid cascading renders
    startTransition(() => {
      setOldName(nextOldName);
      setName(nextName);
      setEditableSearchName(nextSearchName);
      setOperatorValue(step.operator || "");
      setColocationParams(step.colocationParams);
      setRecordTypeValue(nextRecordType);
      setParameters(nextParams);
      setRawParams(nextRawParams);
      setShowRaw(false);
    });
  }, [
    prevStepId,
    paramSpecs,
    recordType,
    step.colocationParams,
    step.displayName,
    step.id,
    step.operator,
    step.parameters,
    step.recordType,
    step.searchName,
  ]);

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

  const handleSave = async () => {
    try {
      const nextName = (name || "").trim() || oldName;
      const nextSearchName = searchName || step.searchName || "";
      let parsedParams = parameters;
      if (showRaw) {
        parsedParams = JSON.parse(rawParams);
      }
      parsedParams = coerceParametersForSpecs(
        parsedParams as Record<string, unknown>,
        paramSpecs,
        // Normal save path: do not accept stringified arrays/CSV.
        { allowStringParsing: false },
      );
      // Do not enforce business-required checks here (backend is authoritative).
      const updates: Partial<StrategyStep> = {
        displayName: nextName,
        parameters: parsedParams as Record<string, unknown>,
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
        const nextOperator = operatorValue || step.operator;
        if (nextOperator) {
          updates.operator = nextOperator as StrategyStep["operator"];
        }
        if (nextOperator === "COLOCATE") {
          updates.colocationParams = colocationParams ?? {
            upstream: 0,
            downstream: 0,
            strand: "both",
          };
        } else {
          updates.colocationParams = undefined;
        }
      }
      let validationError: string | null = null;
      if (!isSearchNameAvailable && kind === "search") {
        validationError =
          "Cannot be saved: search name is not available for this record type.";
      }
      if (
        kind === "search" &&
        resolvedRecordType &&
        nextSearchName &&
        !validationError
      ) {
        try {
          const response: SearchValidationResponse = await validateSearchParams(
            siteId,
            resolvedRecordType,
            nextSearchName,
            parsedParams as Record<string, unknown>,
          );
          const formatted = formatSearchValidationResponse(response);
          if (formatted.message) {
            validationError = formatted.message;
          }
        } catch (err) {
          validationError = `Cannot be saved: ${toUserMessage(err, "validation failed.")}`;
        }
      }
      updates.validationError = validationError || undefined;
      onUpdate(updates);
      onClose();
    } catch {
      setError("Invalid JSON in parameters");
    }
  };

  return (
    <Modal open onClose={onClose} title="Edit step" maxWidth="max-w-4xl">
      <StepEditorHeader onClose={onClose} />

      {/* Content */}
      <div className="max-h-[80vh] space-y-4 overflow-y-auto px-5 py-4">
        {stepValidationError && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">
            {stepValidationError}
          </div>
        )}
        <StepNameFields oldName={oldName} name={name} onNameChange={setName} />

        {(kind === "search" || kind === "transform") && (
          <>
            <StepSearchSelector
              siteId={siteId}
              stepType={kind}
              recordTypeFilter={recordTypeFilter}
              onRecordTypeFilterChange={setRecordTypeFilter}
              filteredRecordTypes={filteredRecordTypes}
              normalizedRecordTypeValue={normalizedRecordTypeValue}
              onRecordTypeValueChange={setRecordTypeValue}
              editableSearchName={editableSearchName}
              onSearchNameChange={setEditableSearchName}
              isLoadingSearches={isLoadingSearches}
              searchOptions={searchOptions}
              filteredSearchOptions={filteredSearchOptions}
              searchName={searchName}
              selectedSearch={selectedSearch}
              isSearchNameAvailable={isSearchNameAvailable}
              searchListError={searchListError}
              recordTypeValue={recordTypeValue ?? null}
              recordType={recordType}
              recordTypeOptions={recordTypeOptions}
            />

            <StepParamFields
              paramSpecs={paramSpecs}
              showRaw={showRaw}
              parameters={parameters}
              vocabOptions={vocabOptions}
              dependentOptions={dependentOptions}
              dependentLoading={dependentLoading}
              dependentErrors={dependentErrors}
              validationErrorKeys={validationErrorKeys}
              setParameters={setParameters}
            />

            <StepRawParamsEditor
              showRaw={showRaw}
              rawParams={rawParams}
              error={error}
              isLoading={isLoading}
              onShowRawChange={setShowRaw}
              onRawParamsChange={(nextValue) => {
                setRawParams(nextValue);
                setError(null);
              }}
            />
          </>
        )}

        {kind === "combine" && (
          <StepCombineOperatorSelect
            operatorValue={operatorValue}
            onOperatorChange={setOperatorValue}
            colocationParams={colocationParams}
            onColocationParamsChange={setColocationParams}
          />
        )}
      </div>

      <StepEditorFooter onClose={onClose} onSave={handleSave} />
    </Modal>
  );
}
