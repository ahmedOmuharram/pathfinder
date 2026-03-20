"use client";

import { useState, useMemo, useCallback } from "react";
import type { ParamSpec } from "@/features/strategy/parameters/spec";
import type { StepParameters } from "@/lib/strategyGraph/types";
import {
  type PhyleticNode,
  type TriState,
  buildPhyleticTree,
  encodeProfilePattern,
  decodeProfilePattern,
  buildSpeciesLists,
  nextTriState,
  triStateIcon,
  triStateColor,
  collectCodes,
  buildCodeToLabel,
  nodeMatchesSearch,
  defaultExpanded,
} from "./phyleticProfileLogic";

export { claimsPhyleticParams } from "./phyleticProfileLogic";

type CompositeWidgetProps = {
  specs: ParamSpec[];
  allSpecs: ParamSpec[];
  parameters: StepParameters;
  onChange: (updates: StepParameters) => void;
};

// ---------------------------------------------------------------------------
// Extract vocab from spec
// ---------------------------------------------------------------------------

function findSpecVocab(specs: ParamSpec[], name: string): unknown {
  const spec = specs.find((s) => s.name === name);
  return spec?.vocabulary;
}

// ---------------------------------------------------------------------------
// Tree node component
// ---------------------------------------------------------------------------

type TreeNodeProps = {
  node: PhyleticNode;
  states: Map<string, TriState>;
  expanded: Set<string>;
  searchQuery: string;
  onToggleState: (code: string) => void;
  onToggleExpand: (code: string) => void;
};

function TreeNodeRow({
  node,
  states,
  expanded,
  searchQuery,
  onToggleState,
  onToggleExpand,
}: TreeNodeProps) {
  const query = searchQuery.toLowerCase();
  if (query && !nodeMatchesSearch(node, query)) return null;

  const state = states.get(node.code) ?? "unconstrained";
  const isExpanded = expanded.has(node.code);
  const hasChildren = node.children.length > 0;
  const indent = (node.depth - 1) * 16;

  return (
    <div>
      <div
        className="flex items-center gap-1 py-0.5 hover:bg-muted/50 rounded px-1"
        style={{ paddingLeft: `${indent}px` }}
        data-node={node.code}
      >
        {hasChildren ? (
          <button
            type="button"
            className="w-4 text-xs text-muted-foreground shrink-0"
            onClick={() => onToggleExpand(node.code)}
            aria-label={isExpanded ? "Collapse" : "Expand"}
          >
            {isExpanded ? "\u25BE" : "\u25B8"}
          </button>
        ) : (
          <span className="w-4 shrink-0" />
        )}
        <button
          type="button"
          className={`w-5 text-center font-bold shrink-0 ${triStateColor(state)}`}
          data-toggle={node.code}
          onClick={() => onToggleState(node.code)}
          aria-label={`Toggle ${node.label}`}
        >
          {triStateIcon(state)}
        </button>
        <span className="text-sm text-foreground truncate">{node.label}</span>
      </div>
      {hasChildren && isExpanded && (
        <div>
          {node.children.map((child) => (
            <TreeNodeRow
              key={child.code}
              node={child}
              states={states}
              expanded={expanded}
              searchQuery={searchQuery}
              onToggleState={onToggleState}
              onToggleExpand={onToggleExpand}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function PhyleticProfileParam({
  specs,
  parameters,
  onChange,
}: CompositeWidgetProps) {
  // Build tree from vocab data
  const termMapVocab =
    parameters["phyletic_term_map"] ?? findSpecVocab(specs, "phyletic_term_map");
  const indentMapVocab =
    parameters["phyletic_indent_map"] ?? findSpecVocab(specs, "phyletic_indent_map");

  const tree = useMemo(
    () => buildPhyleticTree(termMapVocab, indentMapVocab),
    [termMapVocab, indentMapVocab],
  );

  const codeToLabel = useMemo(() => buildCodeToLabel(tree), [tree]);

  // Initialize state from current profile_pattern
  const initialPattern = String(parameters["profile_pattern"] ?? "");
  const [states, setStates] = useState<Map<string, TriState>>(() =>
    decodeProfilePattern(initialPattern),
  );

  const [expanded, setExpanded] = useState<Set<string>>(() => defaultExpanded(tree, 3));

  const [searchQuery, setSearchQuery] = useState("");

  // Compute summary counts
  const allCodes = useMemo(() => collectCodes(tree), [tree]);
  const summary = useMemo(() => {
    let included = 0;
    let excluded = 0;
    let unconstrained = 0;
    for (const code of allCodes) {
      const s = states.get(code) ?? "unconstrained";
      if (s === "include") included++;
      else if (s === "exclude") excluded++;
      else unconstrained++;
    }
    return { included, excluded, unconstrained };
  }, [allCodes, states]);

  const handleToggleState = useCallback(
    (code: string) => {
      setStates((prev) => {
        const next = new Map(prev);
        const current = next.get(code) ?? "unconstrained";
        const newState = nextTriState(current);
        if (newState === "unconstrained") {
          next.delete(code);
        } else {
          next.set(code, newState);
        }

        // Fire onChange with all 5 params
        const pattern = encodeProfilePattern(next);
        const { included, excluded } = buildSpeciesLists(next, codeToLabel);
        onChange({
          profile_pattern: pattern,
          included_species: included,
          excluded_species: excluded,
          phyletic_indent_map: parameters["phyletic_indent_map"],
          phyletic_term_map: parameters["phyletic_term_map"],
        });

        return next;
      });
    },
    [codeToLabel, onChange, parameters],
  );

  const handleToggleExpand = useCallback((code: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(code)) {
        next.delete(code);
      } else {
        next.add(code);
      }
      return next;
    });
  }, []);

  return (
    <div className="rounded-lg border border-border bg-card p-3 space-y-2">
      {/* Search */}
      <input
        type="text"
        placeholder="Search species..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      />

      {/* Legend */}
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span>
          <span className="text-muted-foreground font-bold">{"\u25CB"}</span>{" "}
          unconstrained
        </span>
        <span>
          <span className="text-green-500 font-bold">{"\u2713"}</span> include
        </span>
        <span>
          <span className="text-red-500 font-bold">{"\u2717"}</span> exclude
        </span>
      </div>

      {/* Tree */}
      <div className="max-h-80 overflow-y-auto">
        {tree.map((node) => (
          <TreeNodeRow
            key={node.code}
            node={node}
            states={states}
            expanded={expanded}
            searchQuery={searchQuery}
            onToggleState={handleToggleState}
            onToggleExpand={handleToggleExpand}
          />
        ))}
      </div>

      {/* Summary footer */}
      <div className="text-xs text-muted-foreground border-t border-border pt-2">
        {summary.included} included &middot; {summary.excluded} excluded &middot;{" "}
        {summary.unconstrained} unconstrained
      </div>
    </div>
  );
}
