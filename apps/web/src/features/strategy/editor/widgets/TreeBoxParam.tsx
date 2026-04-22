"use client";

import { useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { cn } from "@/lib/utils/cn";
import { isMultiParam } from "@/features/strategy/parameters/spec";
import type { VocabNode } from "@/lib/utils/vocab";
import type { ParamWidgetProps, ParamFieldApi } from "./types";
import { CheckboxParam } from "./CheckboxParam";

function collectLeaves(node: VocabNode): string[] {
  if (node.children == null || node.children.length === 0) return [node.value];
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
    if (node.children != null && node.children.length > 0) {
      result.add(node.value);
      for (const v of buildDefaultExpanded(node.children, depth + 1)) {
        result.add(v);
      }
    }
  }
  return result;
}

export function TreeBoxParam({ spec, name, options, vocabTree, field }: ParamWidgetProps) {
  if (!vocabTree) {
    return <CheckboxParam spec={spec} name={name} options={options} vocabTree={null} field={field} />;
  }

  return <TreeBoxInner spec={spec} name={name} vocabTree={vocabTree} field={field} />;
}

function TreeBoxInner({
  spec,
  name,
  vocabTree,
  field,
}: {
  spec: ParamWidgetProps["spec"];
  name: string;
  vocabTree: VocabNode[];
  field: ParamFieldApi;
}) {
  const multi = isMultiParam(spec);

  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(() =>
    buildDefaultExpanded(vocabTree),
  );
  const [searchTerm, setSearchTerm] = useState("");

  const allLeaves = collectAllLeaves(vocabTree);

  const toggleExpand = (nodeValue: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeValue)) {
        next.delete(nodeValue);
      } else {
        next.add(nodeValue);
      }
      return next;
    });
  };

  const lowerSearch = searchTerm.toLowerCase();

  const errors = field.state.meta.errors;
  const hasError = errors.length > 0;
  const errorMessage = hasError ? String(errors[0]) : null;

  const currentValue: string[] = multi
    ? (Array.isArray(field.state.value)
        ? (field.state.value as unknown[]).filter(
            (v): v is string => typeof v === "string",
          )
        : [])
    : [];
  const selectedSet = new Set(currentValue);

  const toggleBranch = (node: VocabNode) => {
    const leaves = collectLeaves(node);
    const allChecked = leaves.every((l) => selectedSet.has(l));
    if (allChecked) {
      field.handleChange(currentValue.filter((v) => !leaves.includes(v)));
    } else {
      const next = [...currentValue];
      for (const l of leaves) {
        if (!next.includes(l)) next.push(l);
      }
      field.handleChange(next);
    }
  };

  const toggleLeaf = (leafValue: string) => {
    if (selectedSet.has(leafValue)) {
      field.handleChange(currentValue.filter((v) => v !== leafValue));
    } else {
      field.handleChange([...currentValue, leafValue]);
    }
  };

  const singleValue = !multi && typeof field.state.value === "string" ? field.state.value : "";

  function renderNode(node: VocabNode, depth: number) {
    if (lowerSearch && !nodeMatchesSearch(node, lowerSearch)) {
      return null;
    }

    const isBranch = Boolean(node.children != null && node.children.length > 0);
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
              <Checkbox
                checked={allChecked ? true : someChecked ? "indeterminate" : false}
                onCheckedChange={() => (isBranch ? toggleBranch(node) : toggleLeaf(node.value))}
                onBlur={field.handleBlur}
                aria-label={node.label}
              />
            ) : !isBranch ? (
              <RadioGroupItem value={node.value} aria-label={node.label} />
            ) : null}
            {node.label}
          </label>
        </div>
        {isBranch &&
          isExpanded &&
          node.children?.map((child) => renderNode(child, depth + 1))}
      </div>
    );
  }

  const selectedCount = currentValue.filter((v) => allLeaves.includes(v)).length;

  const treeBody = (
    <div
      aria-invalid={hasError ? "true" : undefined}
      aria-describedby={hasError ? `${name}-error` : undefined}
      className={cn(
        "rounded-md border bg-card text-sm",
        hasError ? "border-destructive/30 bg-destructive/5" : "border-border",
      )}
    >
      <div className="p-2 border-b border-border">
        <Input
          type="text"
          placeholder="Search..."
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
        />
      </div>
      <div className="max-h-64 overflow-y-auto p-2">
        {vocabTree.map((node) => renderNode(node, 0))}
      </div>
      {multi && (
        <div className="px-2 py-1.5 border-t border-border text-xs text-muted-foreground">
          {selectedCount} of {allLeaves.length} selected
        </div>
      )}
    </div>
  );

  return (
    <div>
      {multi ? (
        treeBody
      ) : (
        <RadioGroup
          value={singleValue}
          onValueChange={(next) => field.handleChange(next)}
        >
          {treeBody}
        </RadioGroup>
      )}
      {hasError && errorMessage != null && (
        <p id={`${name}-error`} role="alert" className="mt-1 text-xs text-destructive">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
