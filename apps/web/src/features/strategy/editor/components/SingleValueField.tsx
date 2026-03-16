"use client";

import type { Dispatch, SetStateAction } from "react";
import type { VocabOption, VocabNode } from "@/lib/utils/vocab";
import type { ParamSpec } from "@/features/strategy/parameters/spec";
import type { StepParameters } from "@/lib/strategyGraph/types";
import { Input } from "@/lib/components/ui/Input";

type SingleValueFieldProps = {
  paramName: string;
  spec: ParamSpec;
  value: unknown;
  options: VocabOption[];
  vocabTree: VocabNode[] | null;
  normalizedValue: string[];
  fieldBorderClass: string;
  setParameters: Dispatch<SetStateAction<StepParameters>>;
};

export function SingleValueField({
  paramName,
  spec,
  value,
  options,
  vocabTree,
  normalizedValue,
  fieldBorderClass,
  setParameters,
}: SingleValueFieldProps) {
  if (vocabTree) {
    return (
      <SingleTreePicker
        paramName={paramName}
        vocabTree={vocabTree}
        selectedValue={normalizedValue[0] || ""}
        setParameters={setParameters}
      />
    );
  }

  if (options.length > 0) {
    return (
      <div
        className={`space-y-1 rounded-md border px-2 py-2 text-sm text-foreground ${fieldBorderClass}`}
      >
        {options.map((opt) => (
          <label key={opt.value} className="flex items-center gap-2">
            <input
              type="radio"
              name={`param-${paramName}`}
              value={opt.value}
              checked={normalizedValue[0] === opt.value}
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
    );
  }

  return (
    <TextInput
      paramName={paramName}
      spec={spec}
      value={value}
      fieldBorderClass={fieldBorderClass}
      setParameters={setParameters}
    />
  );
}

// ---------------------------------------------------------------------------
// Single-value tree picker (radio buttons in a tree)
// ---------------------------------------------------------------------------

function SingleTreePicker({
  paramName,
  vocabTree,
  selectedValue,
  setParameters,
}: {
  paramName: string;
  vocabTree: VocabNode[];
  selectedValue: string;
  setParameters: Dispatch<SetStateAction<StepParameters>>;
}) {
  const renderNode = (node: VocabNode, depth = 0) => (
    <div key={node.value}>
      <label className="flex items-center gap-2" style={{ paddingLeft: depth * 12 }}>
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

  return (
    <div className="space-y-1 rounded-md border border-border bg-card px-2 py-2 text-sm text-foreground">
      {vocabTree.map((node) => renderNode(node))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Text / number input fallback
// ---------------------------------------------------------------------------

function TextInput({
  paramName,
  spec,
  value,
  fieldBorderClass,
  setParameters,
}: {
  paramName: string;
  spec: ParamSpec;
  value: unknown;
  fieldBorderClass: string;
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
      className={fieldBorderClass}
    />
  );
}
