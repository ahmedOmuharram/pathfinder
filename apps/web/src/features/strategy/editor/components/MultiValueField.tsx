"use client";

import type { Dispatch, SetStateAction } from "react";
import { collectNodeValues, type VocabOption, type VocabNode } from "@/lib/utils/vocab";
import { coerceMultiValue } from "@/features/strategy/parameters/coerce";
import type { ParamSpec } from "@/features/strategy/parameters/spec";
import type { StepParameters } from "@/lib/strategyGraph/types";
import { Input } from "@/lib/components/ui/Input";

type MultiValueFieldProps = {
  paramName: string;
  spec: ParamSpec;
  value: unknown;
  options: VocabOption[];
  vocabTree: VocabNode[] | null;
  fieldBorderClass: string;
  setParameters: Dispatch<SetStateAction<StepParameters>>;
};

export function MultiValueField({
  paramName,
  spec,
  value,
  options,
  vocabTree,
  fieldBorderClass,
  setParameters,
}: MultiValueFieldProps) {
  if (vocabTree) {
    return (
      <MultiTreePicker
        paramName={paramName}
        vocabTree={vocabTree}
        value={value}
        fieldBorderClass={fieldBorderClass}
        setParameters={setParameters}
      />
    );
  }

  if (options.length > 0) {
    return (
      <MultiCheckboxList
        paramName={paramName}
        options={options}
        value={value}
        setParameters={setParameters}
      />
    );
  }

  return (
    <MultiTextInput
      paramName={paramName}
      spec={spec}
      value={value}
      setParameters={setParameters}
    />
  );
}

// ---------------------------------------------------------------------------
// Multi-value tree picker (checkboxes in a tree)
// ---------------------------------------------------------------------------

function MultiTreePicker({
  paramName,
  vocabTree,
  value,
  fieldBorderClass,
  setParameters,
}: {
  paramName: string;
  vocabTree: VocabNode[];
  value: unknown;
  fieldBorderClass: string;
  setParameters: Dispatch<SetStateAction<StepParameters>>;
}) {
  const allValues = vocabTree
    .flatMap((node) => collectNodeValues(node))
    .filter((val) => val !== "@@fake@@");

  const normalizedValues = coerceMultiValue(value, { allowStringParsing: false });
  const selectedValues = new Set(
    normalizedValues.includes("@@fake@@") ? allValues : normalizedValues,
  );

  const allSelected =
    allValues.length > 0 &&
    selectedValues.size === allValues.length &&
    allValues.every((val) => selectedValues.has(val));
  const noneSelected = selectedValues.size === 0;

  const toggleNode = (node: VocabNode) => {
    if (node.value === "@@fake@@") {
      const next = allSelected ? [] : allValues;
      setParameters((prev) => ({ ...prev, [paramName]: next }));
      return;
    }
    const nodeValues = collectNodeValues(node).filter((val) => val !== "@@fake@@");
    const isChecked = nodeValues.every((val) => selectedValues.has(val));
    const next = new Set(selectedValues);
    if (isChecked) {
      nodeValues.forEach((val) => next.delete(val));
    } else {
      nodeValues.forEach((val) => next.add(val));
    }
    setParameters((prev) => ({ ...prev, [paramName]: Array.from(next) }));
  };

  const renderNode = (node: VocabNode, depth = 0) => {
    const nodeValues = collectNodeValues(node);
    const isChecked = nodeValues.every((val) => selectedValues.has(val));
    const isPartial = !isChecked && nodeValues.some((val) => selectedValues.has(val));
    return (
      <div key={node.value}>
        <label className="flex items-center gap-2" style={{ paddingLeft: depth * 12 }}>
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
        {node.children?.map((child) => renderNode(child, depth + 1))}
      </div>
    );
  };

  return (
    <div
      className={`space-y-1 rounded-md border px-2 py-2 text-sm text-foreground ${fieldBorderClass}`}
    >
      {vocabTree.map((node) => renderNode(node))}
      <div className="mt-2 text-xs text-muted-foreground">
        {allSelected
          ? "All selected (WDK default)."
          : noneSelected
            ? "None selected."
            : `${selectedValues.size} selected.`}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Multi-value flat checkbox list
// ---------------------------------------------------------------------------

function MultiCheckboxList({
  paramName,
  options,
  value,
  setParameters,
}: {
  paramName: string;
  options: VocabOption[];
  value: unknown;
  setParameters: Dispatch<SetStateAction<StepParameters>>;
}) {
  const allValues = options.map((opt) => opt.value).filter((val) => val !== "@@fake@@");

  const normalizedValues = coerceMultiValue(value, { allowStringParsing: false });
  const selectedValues = new Set(
    normalizedValues.includes("@@fake@@") ? allValues : normalizedValues,
  );

  const toggleValue = (nextValue: string) => {
    if (nextValue === "@@fake@@") {
      const isAllSelected =
        selectedValues.size === allValues.length &&
        allValues.every((val) => selectedValues.has(val));
      const next = isAllSelected ? [] : allValues;
      setParameters((prev) => ({ ...prev, [paramName]: next }));
      return;
    }
    const next = new Set(selectedValues);
    if (next.has(nextValue)) {
      next.delete(nextValue);
    } else {
      next.add(nextValue);
    }
    setParameters((prev) => ({ ...prev, [paramName]: Array.from(next) }));
  };

  return (
    <div className="space-y-1 rounded-md border border-border bg-card px-2 py-2 text-sm text-foreground">
      {options.map((opt) => (
        <label key={opt.value} className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={selectedValues.has(opt.value)}
            onChange={() => toggleValue(opt.value)}
            className="h-3.5 w-3.5 rounded border-input text-foreground"
          />
          <span>{opt.displayLabel ?? opt.label}</span>
        </label>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Multi-value text input fallback
// ---------------------------------------------------------------------------

function MultiTextInput({
  paramName,
  spec,
  value,
  setParameters,
}: {
  paramName: string;
  spec: ParamSpec;
  value: unknown;
  setParameters: Dispatch<SetStateAction<StepParameters>>;
}) {
  const isNumeric = ["number", "integer", "float"].includes(
    (spec.type || "").toLowerCase(),
  );

  return (
    <Input
      type={isNumeric ? "number" : "text"}
      value={value === undefined || value === null ? "" : String(value)}
      onChange={(event) => {
        const raw = event.currentTarget.value;
        setParameters((prev) => ({
          ...prev,
          [paramName]: isNumeric ? Number(raw) : raw,
        }));
      }}
      className="bg-card"
    />
  );
}
