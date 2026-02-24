"use client";

import type { Dispatch, SetStateAction } from "react";
import {
  collectNodeValues,
  extractSpecVocabulary,
  extractVocabTree,
  type VocabOption,
  type VocabNode,
} from "./stepEditorUtils";
import { isMultiParam, type ParamSpec } from "@/features/strategy/parameters/spec";
import { coerceMultiValue } from "@/features/strategy/parameters/coerce";

type StepParamFieldsProps = {
  paramSpecs: ParamSpec[];
  showRaw: boolean;
  parameters: Record<string, unknown>;
  vocabOptions: Record<string, VocabOption[]>;
  dependentOptions: Record<string, VocabOption[]>;
  dependentLoading: Record<string, boolean>;
  dependentErrors: Record<string, string | null>;
  validationErrorKeys: Set<string>;
  setParameters: Dispatch<SetStateAction<Record<string, unknown>>>;
};

export function StepParamFields({
  paramSpecs,
  showRaw,
  parameters,
  vocabOptions,
  dependentOptions,
  dependentLoading,
  dependentErrors,
  validationErrorKeys,
  setParameters,
}: StepParamFieldsProps) {
  if (showRaw) return null;

  if (paramSpecs.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No parameter options available. Use advanced editing to view or edit raw JSON.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {paramSpecs.map((spec) => {
        if (!spec.name) return null;
        const paramName = spec.name;
        const label = spec.displayName || paramName;
        const options = vocabOptions[paramName] || dependentOptions[paramName] || [];
        const value = parameters[paramName];
        const multi = isMultiParam(spec);
        const vocabulary = extractSpecVocabulary(spec);
        const vocabTree = multi ? extractVocabTree(vocabulary) : null;
        const valueSet = new Set(options.map((opt) => opt.value));
        const labelToValue = new Map(
          options.map((opt) => [opt.rawLabel ?? opt.label, opt.value]),
        );
        const normalizeValue = (raw: unknown): string[] => {
          if (raw === null || raw === undefined) return [];
          const list = Array.isArray(raw) ? raw : [raw];
          return list
            .map((entry) => {
              const str = String(entry);
              if (valueSet.has(str)) return str;
              return labelToValue.get(str) || str;
            })
            .filter((entry) => entry !== "");
        };
        const hasFieldError = validationErrorKeys.has(paramName);
        const fieldWrapperClass = hasFieldError
          ? "rounded-md border border-destructive/20 bg-destructive/5 p-2"
          : "";
        const fieldLabelClass = hasFieldError
          ? "mb-1 block text-xs font-semibold uppercase tracking-wide text-destructive"
          : "mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground";
        const fieldBorderClass = hasFieldError
          ? "border-destructive/30 bg-destructive/5"
          : "border-border bg-card";
        return (
          <div key={paramName} className={fieldWrapperClass}>
            <label className={fieldLabelClass}>
              {label}
              {spec.allowEmptyValue === false && (
                <span className="ml-1 text-destructive">*</span>
              )}
            </label>
            <>
              {multi ? (
                vocabTree ? (
                  <div
                    className={`space-y-1 rounded-md border px-2 py-2 text-sm text-foreground ${fieldBorderClass}`}
                  >
                    {(() => {
                      const allValues = vocabTree
                        .flatMap((node) => collectNodeValues(node))
                        .filter((val) => val !== "@@fake@@");
                      const normalizedValues = coerceMultiValue(value, {
                        allowStringParsing: false,
                      });
                      const selectedValues = new Set(
                        normalizedValues.includes("@@fake@@")
                          ? allValues
                          : normalizedValues,
                      );
                      const allSelected =
                        allValues.length > 0 &&
                        selectedValues.size === allValues.length &&
                        allValues.every((val) => selectedValues.has(val));
                      const noneSelected = selectedValues.size === 0;
                      const toggleNode = (node: VocabNode) => {
                        if (node.value === "@@fake@@") {
                          const next = allSelected ? [] : allValues;
                          setParameters((prev) => ({
                            ...prev,
                            [paramName]: next,
                          }));
                          return;
                        }
                        const nodeValues = collectNodeValues(node).filter(
                          (val) => val !== "@@fake@@",
                        );
                        const isChecked = nodeValues.every((val) =>
                          selectedValues.has(val),
                        );
                        const next = new Set(selectedValues);
                        if (isChecked) {
                          nodeValues.forEach((val) => next.delete(val));
                        } else {
                          nodeValues.forEach((val) => next.add(val));
                        }
                        setParameters((prev) => ({
                          ...prev,
                          [paramName]: Array.from(next),
                        }));
                      };
                      const renderNode = (node: VocabNode, depth = 0) => {
                        const nodeValues = collectNodeValues(node);
                        const isChecked = nodeValues.every((val) =>
                          selectedValues.has(val),
                        );
                        const isPartial =
                          !isChecked &&
                          nodeValues.some((val) => selectedValues.has(val));
                        return (
                          <div key={node.value}>
                            <label
                              className="flex items-center gap-2"
                              style={{ paddingLeft: depth * 12 }}
                            >
                              <input
                                type="checkbox"
                                checked={isChecked}
                                ref={(el) => {
                                  if (el) el.indeterminate = isPartial;
                                }}
                                onChange={() => toggleNode(node)}
                                className="h-3.5 w-3.5 rounded border-input text-foreground"
                              />
                              <span>{node.label}</span>
                            </label>
                            {node.children?.map((child) =>
                              renderNode(child, depth + 1),
                            )}
                          </div>
                        );
                      };
                      return (
                        <>
                          {vocabTree.map((node) => renderNode(node))}
                          <div className="mt-2 text-xs text-muted-foreground">
                            {allSelected
                              ? "All selected (WDK default)."
                              : noneSelected
                                ? "None selected."
                                : `${selectedValues.size} selected.`}
                          </div>
                        </>
                      );
                    })()}
                  </div>
                ) : options.length > 0 ? (
                  <div className="space-y-1 rounded-md border border-border bg-card px-2 py-2 text-sm text-foreground">
                    {(() => {
                      const allValues = options
                        .map((opt) => opt.value)
                        .filter((val) => val !== "@@fake@@");
                      const normalizedValues = coerceMultiValue(value, {
                        allowStringParsing: false,
                      });
                      const selectedValues = new Set(
                        normalizedValues.includes("@@fake@@")
                          ? allValues
                          : normalizedValues,
                      );
                      const toggleValue = (nextValue: string) => {
                        if (nextValue === "@@fake@@") {
                          const isAllSelected =
                            selectedValues.size === allValues.length &&
                            allValues.every((val) => selectedValues.has(val));
                          const next = isAllSelected ? [] : allValues;
                          setParameters((prev) => ({
                            ...prev,
                            [paramName]: next,
                          }));
                          return;
                        }
                        const next = new Set(selectedValues);
                        if (next.has(nextValue)) {
                          next.delete(nextValue);
                        } else {
                          next.add(nextValue);
                        }
                        setParameters((prev) => ({
                          ...prev,
                          [paramName]: Array.from(next),
                        }));
                      };
                      return options.map((opt) => (
                        <label key={opt.value} className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={selectedValues.has(opt.value)}
                            onChange={() => toggleValue(opt.value)}
                            className="h-3.5 w-3.5 rounded border-input text-foreground"
                          />
                          <span>{opt.displayLabel ?? opt.label}</span>
                        </label>
                      ));
                    })()}
                  </div>
                ) : (
                  <input
                    type={
                      ["number", "integer", "float"].includes(
                        (spec.type || "").toLowerCase(),
                      )
                        ? "number"
                        : "text"
                    }
                    value={value === undefined || value === null ? "" : String(value)}
                    onChange={(event) => {
                      const raw = event.currentTarget.value;
                      setParameters((prev) => ({
                        ...prev,
                        [paramName]: ["number", "integer", "float"].includes(
                          (spec.type || "").toLowerCase(),
                        )
                          ? Number(raw)
                          : raw,
                      }));
                    }}
                    className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground"
                  />
                )
              ) : vocabTree ? (
                <div className="space-y-1 rounded-md border border-border bg-card px-2 py-2 text-sm text-foreground">
                  {(() => {
                    const selectedValue = normalizeValue(value)[0] || "";
                    const renderNode = (node: VocabNode, depth = 0) => (
                      <div key={node.value}>
                        <label
                          className="flex items-center gap-2"
                          style={{ paddingLeft: depth * 12 }}
                        >
                          <input
                            type="radio"
                            name={`param-${paramName}`}
                            value={node.value}
                            checked={selectedValue === node.value}
                            onChange={() => {
                              setParameters((prev) => ({
                                ...prev,
                                [paramName]: node.value,
                              }));
                            }}
                            className="h-3.5 w-3.5 border-input text-foreground"
                          />
                          <span>{node.label}</span>
                        </label>
                        {node.children?.map((child) => renderNode(child, depth + 1))}
                      </div>
                    );
                    return vocabTree.map((node) => renderNode(node));
                  })()}
                </div>
              ) : options.length > 0 ? (
                <div
                  className={`space-y-1 rounded-md border px-2 py-2 text-sm text-foreground ${fieldBorderClass}`}
                >
                  {options.map((opt) => (
                    <label key={opt.value} className="flex items-center gap-2">
                      <input
                        type="radio"
                        name={`param-${paramName}`}
                        value={opt.value}
                        checked={normalizeValue(value)[0] === opt.value}
                        onChange={() => {
                          setParameters((prev) => ({
                            ...prev,
                            [paramName]: opt.value,
                          }));
                        }}
                        className="h-3.5 w-3.5 border-input text-foreground"
                      />
                      <span>{opt.displayLabel ?? opt.label}</span>
                    </label>
                  ))}
                </div>
              ) : (
                <input
                  type={
                    ["number", "integer", "float"].includes(
                      (spec.type || "").toLowerCase(),
                    )
                      ? "number"
                      : "text"
                  }
                  value={value === undefined || value === null ? "" : String(value)}
                  onChange={(event) => {
                    const raw = event.currentTarget.value;
                    setParameters((prev) => ({
                      ...prev,
                      [paramName]: ["number", "integer", "float"].includes(
                        (spec.type || "").toLowerCase(),
                      )
                        ? Number(raw)
                        : raw,
                    }));
                  }}
                  className={`w-full rounded-md border px-3 py-2 text-sm text-foreground ${fieldBorderClass}`}
                />
              )}
              <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                {dependentLoading[paramName] && <span>Loading options...</span>}
                {dependentErrors[paramName] && (
                  <span className="text-destructive">{dependentErrors[paramName]}</span>
                )}
                {options.length === 0 && (
                  <span className="text-muted-foreground">
                    Use advanced editing if needed.
                  </span>
                )}
              </div>
            </>
            {spec.help && (
              <p className="mt-1 text-xs text-muted-foreground">{spec.help}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
