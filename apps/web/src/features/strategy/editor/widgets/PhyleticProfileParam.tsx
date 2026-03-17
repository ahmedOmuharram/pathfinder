"use client";

import { useState, useMemo, useCallback } from "react";
import type { ParamSpec } from "@/features/strategy/parameters/spec";
import type { StepParameters } from "@/lib/strategyGraph/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CompositeWidgetProps = {
  specs: ParamSpec[];
  allSpecs: ParamSpec[];
  parameters: StepParameters;
  onChange: (updates: StepParameters) => void;
};

export type PhyleticNode = {
  code: string;
  label: string;
  depth: number;
  children: PhyleticNode[];
};

export type TriState = "unconstrained" | "include" | "exclude";

// ---------------------------------------------------------------------------
// Claimed param names
// ---------------------------------------------------------------------------

const PHYLETIC_PARAM_NAMES = [
  "profile_pattern",
  "included_species",
  "excluded_species",
  "phyletic_indent_map",
  "phyletic_term_map",
] as const;

export function claimsPhyleticParams(specs: ParamSpec[]): string[] {
  const names = new Set(specs.map((s) => s.name).filter(Boolean));
  const allPresent = PHYLETIC_PARAM_NAMES.every((n) => names.has(n));
  return allPresent ? [...PHYLETIC_PARAM_NAMES] : [];
}

// ---------------------------------------------------------------------------
// Tree building
// ---------------------------------------------------------------------------

export function buildPhyleticTree(
  termMapVocab: unknown,
  indentMapVocab: unknown,
): PhyleticNode[] {
  const terms: Array<[string, string]> = [];
  const indents: Map<string, number> = new Map();

  if (Array.isArray(termMapVocab)) {
    for (const entry of termMapVocab) {
      if (Array.isArray(entry) && entry.length >= 2) {
        terms.push([String(entry[0]), String(entry[1])]);
      }
    }
  }
  if (Array.isArray(indentMapVocab)) {
    for (const entry of indentMapVocab) {
      if (Array.isArray(entry) && entry.length >= 2) {
        indents.set(String(entry[0]), Number(entry[1]));
      }
    }
  }

  const roots: PhyleticNode[] = [];
  const stack: PhyleticNode[] = [];

  for (const [code, label] of terms) {
    if (code === "ALL") continue;
    const depth = indents.get(code) ?? 1;
    const node: PhyleticNode = { code, label, depth, children: [] };

    while (stack.length > 0 && stack[stack.length - 1].depth >= depth) {
      stack.pop();
    }

    if (stack.length === 0) {
      roots.push(node);
    } else {
      stack[stack.length - 1].children.push(node);
    }
    stack.push(node);
  }

  return roots;
}

// ---------------------------------------------------------------------------
// Profile pattern encode/decode
// ---------------------------------------------------------------------------

export function encodeProfilePattern(states: Map<string, TriState>): string {
  const entries: string[] = [];
  for (const [code, state] of states) {
    if (state === "include") entries.push(`${code}>=1T`);
    else if (state === "exclude") entries.push(`${code}=0T`);
  }
  return entries.join(",");
}

export function decodeProfilePattern(pattern: string): Map<string, TriState> {
  const states = new Map<string, TriState>();
  if (!pattern) return states;
  for (const entry of pattern.split(",")) {
    const trimmed = entry.trim();
    if (!trimmed) continue;
    const includeMatch = trimmed.match(/^([^>=]+)>=1T$/);
    if (includeMatch) {
      states.set(includeMatch[1], "include");
      continue;
    }
    const excludeMatch = trimmed.match(/^([^>=]+)=0T$/);
    if (excludeMatch) {
      states.set(excludeMatch[1], "exclude");
      continue;
    }
  }
  return states;
}

// ---------------------------------------------------------------------------
// Species lists
// ---------------------------------------------------------------------------

function buildSpeciesLists(
  states: Map<string, TriState>,
  codeToLabel: Map<string, string>,
): { included: string; excluded: string } {
  const included: string[] = [];
  const excluded: string[] = [];
  for (const [code, state] of states) {
    const label = codeToLabel.get(code) ?? code;
    if (state === "include") included.push(label);
    else if (state === "exclude") excluded.push(label);
  }
  return { included: included.join(","), excluded: excluded.join(",") };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function nextTriState(current: TriState): TriState {
  if (current === "unconstrained") return "include";
  if (current === "include") return "exclude";
  return "unconstrained";
}

function triStateIcon(state: TriState): string {
  if (state === "include") return "\u2713";
  if (state === "exclude") return "\u2717";
  return "\u25CB";
}

function triStateColor(state: TriState): string {
  if (state === "include") return "text-green-500";
  if (state === "exclude") return "text-red-500";
  return "text-muted-foreground";
}

/** Collect all codes from a tree */
function collectCodes(nodes: PhyleticNode[]): string[] {
  const codes: string[] = [];
  for (const node of nodes) {
    codes.push(node.code);
    codes.push(...collectCodes(node.children));
  }
  return codes;
}

/** Build code->label map from tree */
function buildCodeToLabel(nodes: PhyleticNode[]): Map<string, string> {
  const map = new Map<string, string>();
  for (const node of nodes) {
    map.set(node.code, node.label);
    for (const [k, v] of buildCodeToLabel(node.children)) {
      map.set(k, v);
    }
  }
  return map;
}

/** Check if a node or any descendant matches the search query */
function nodeMatchesSearch(node: PhyleticNode, query: string): boolean {
  if (node.label.toLowerCase().includes(query)) return true;
  return node.children.some((child) => nodeMatchesSearch(child, query));
}

/** Default expanded depth: top 2 levels */
function defaultExpanded(nodes: PhyleticNode[], maxDepth: number): Set<string> {
  const expanded = new Set<string>();
  function walk(list: PhyleticNode[]) {
    for (const node of list) {
      if (node.children.length > 0 && node.depth < maxDepth) {
        expanded.add(node.code);
        walk(node.children);
      }
    }
  }
  walk(nodes);
  return expanded;
}

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
    parameters.phyletic_term_map ?? findSpecVocab(specs, "phyletic_term_map");
  const indentMapVocab =
    parameters.phyletic_indent_map ?? findSpecVocab(specs, "phyletic_indent_map");

  const tree = useMemo(
    () => buildPhyleticTree(termMapVocab, indentMapVocab),
    [termMapVocab, indentMapVocab],
  );

  const codeToLabel = useMemo(() => buildCodeToLabel(tree), [tree]);

  // Initialize state from current profile_pattern
  const initialPattern = String(parameters.profile_pattern ?? "");
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
          phyletic_indent_map: parameters.phyletic_indent_map,
          phyletic_term_map: parameters.phyletic_term_map,
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
