import { useState, useCallback, useMemo } from "react";
import type { VocabNode } from "@/lib/utils/vocab";
import type { ParamWidgetProps } from "./types";
import { CheckboxParam } from "./CheckboxParam";

function collectLeaves(node: VocabNode): string[] {
  if (!node.children?.length) return [node.value];
  return node.children.flatMap(collectLeaves);
}

function collectAllLeaves(nodes: VocabNode[]): string[] {
  return nodes.flatMap(collectLeaves);
}

function nodeMatchesSearch(node: VocabNode, term: string): boolean {
  if (node.label.toLowerCase().includes(term)) return true;
  if (node.children) {
    return node.children.some((child) => nodeMatchesSearch(child, term));
  }
  return false;
}

function buildDefaultExpanded(nodes: VocabNode[], depth = 0): Set<string> {
  const result = new Set<string>();
  if (depth >= 2) return result;
  for (const node of nodes) {
    if (node.children?.length) {
      result.add(node.value);
      for (const v of buildDefaultExpanded(node.children, depth + 1)) {
        result.add(v);
      }
    }
  }
  return result;
}

export function TreeBoxParam(props: ParamWidgetProps) {
  const {
    spec,
    value,
    multi,
    multiValue,
    options,
    vocabTree,
    onChangeSingle,
    onChangeMulti,
    fieldBorderClass,
  } = props;

  // Flat fallback when no tree structure
  if (!vocabTree) {
    return <CheckboxParam {...props} />;
  }

  return (
    <TreeBoxInner
      spec={spec}
      value={value}
      multi={multi}
      multiValue={multiValue}
      options={options}
      vocabTree={vocabTree}
      onChangeSingle={onChangeSingle}
      onChangeMulti={onChangeMulti}
      fieldBorderClass={fieldBorderClass}
    />
  );
}

function TreeBoxInner({
  spec,
  value,
  multi,
  multiValue,
  vocabTree,
  onChangeSingle,
  onChangeMulti,
  fieldBorderClass,
}: {
  spec: ParamWidgetProps["spec"];
  value: ParamWidgetProps["value"];
  multi: boolean;
  multiValue: string[];
  options: ParamWidgetProps["options"];
  vocabTree: VocabNode[];
  onChangeSingle: ParamWidgetProps["onChangeSingle"];
  onChangeMulti: ParamWidgetProps["onChangeMulti"];
  fieldBorderClass?: string;
}) {
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(() =>
    buildDefaultExpanded(vocabTree),
  );
  const [searchTerm, setSearchTerm] = useState("");

  const allLeaves = collectAllLeaves(vocabTree);
  const selectedSet = useMemo(() => new Set(multiValue), [multiValue]);

  const toggleExpand = useCallback((nodeValue: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeValue)) {
        next.delete(nodeValue);
      } else {
        next.add(nodeValue);
      }
      return next;
    });
  }, []);

  const toggleBranch = useCallback(
    (node: VocabNode) => {
      const leaves = collectLeaves(node);
      const allChecked = leaves.every((l) => selectedSet.has(l));
      if (allChecked) {
        onChangeMulti(multiValue.filter((v) => !leaves.includes(v)));
      } else {
        const next = [...multiValue];
        for (const l of leaves) {
          if (!next.includes(l)) next.push(l);
        }
        onChangeMulti(next);
      }
    },
    [multiValue, onChangeMulti, selectedSet],
  );

  const toggleLeaf = useCallback(
    (leafValue: string) => {
      if (selectedSet.has(leafValue)) {
        onChangeMulti(multiValue.filter((v) => v !== leafValue));
      } else {
        onChangeMulti([...multiValue, leafValue]);
      }
    },
    [multiValue, onChangeMulti, selectedSet],
  );

  const lowerSearch = searchTerm.toLowerCase();

  function renderNode(node: VocabNode, depth: number) {
    if (lowerSearch && !nodeMatchesSearch(node, lowerSearch)) {
      return null;
    }

    const isBranch = Boolean(node.children?.length);
    const isExpanded = expandedNodes.has(node.value);
    const leaves = collectLeaves(node);
    const allChecked = leaves.every((l) => selectedSet.has(l));
    const someChecked = !allChecked && leaves.some((l) => selectedSet.has(l));

    return (
      <div key={node.value}>
        <div
          data-node-row
          className="flex items-center gap-1 py-0.5"
          style={{ paddingLeft: depth * 20 }}
        >
          {isBranch ? (
            <button
              type="button"
              onClick={() => toggleExpand(node.value)}
              className="w-4 h-4 flex items-center justify-center text-muted-foreground"
              aria-label={isExpanded ? "Collapse" : "Expand"}
            >
              <svg
                width="12"
                height="12"
                viewBox="0 0 12 12"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{
                  transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                  transition: "transform 0.15s",
                }}
              >
                <path d="M4 2 L8 6 L4 10" />
              </svg>
            </button>
          ) : (
            <span className="w-4" />
          )}
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            {multi ? (
              <input
                type="checkbox"
                checked={allChecked}
                ref={(el) => {
                  if (el) el.indeterminate = someChecked;
                }}
                onChange={() =>
                  isBranch ? toggleBranch(node) : toggleLeaf(node.value)
                }
                className="accent-primary"
              />
            ) : (
              !isBranch && (
                <input
                  type="radio"
                  name={spec.name}
                  value={node.value}
                  checked={value === node.value}
                  onChange={() => onChangeSingle(node.value)}
                  className="accent-primary"
                />
              )
            )}
            {node.label}
          </label>
        </div>
        {isBranch &&
          isExpanded &&
          node.children?.map((child) => renderNode(child, depth + 1))}
      </div>
    );
  }

  const selectedCount = multiValue.filter((v) => allLeaves.includes(v)).length;

  return (
    <div
      className={`rounded-md border ${fieldBorderClass || "border-border"} bg-card text-sm`}
    >
      <div className="p-2 border-b border-border">
        <input
          type="text"
          placeholder="Search..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full rounded border border-border bg-card px-2 py-1 text-sm text-foreground placeholder:text-muted-foreground"
        />
      </div>
      <div className="max-h-64 overflow-y-auto p-2">
        {vocabTree.map((node) => renderNode(node, 0))}
      </div>
      <div className="px-2 py-1.5 border-t border-border text-xs text-muted-foreground">
        {selectedCount} of {allLeaves.length} selected
      </div>
    </div>
  );
}
