import type { ParamSpec } from "@/features/strategy/parameters/spec";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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

    while (stack.length > 0) {
      const top = stack[stack.length - 1];
      if (top == null || top.depth < depth) break;
      stack.pop();
    }

    if (stack.length === 0) {
      roots.push(node);
    } else {
      const parent = stack[stack.length - 1];
      if (parent != null) {
        parent.children.push(node);
      }
    }
    stack.push(node);
  }

  return roots;
}

// ---------------------------------------------------------------------------
// Profile pattern encode/decode
// ---------------------------------------------------------------------------

export function encodeProfilePattern(states: Map<string, TriState>): string {
  const tokens: string[] = [];
  for (const [code, state] of states) {
    if (state === "include") tokens.push(`${code}:Y`);
    else if (state === "exclude") tokens.push(`${code}:N`);
  }
  // The census lists codes ascending and `%A%B%` means "A, then later B", so
  // tokens out of that order describe a census that cannot exist.
  tokens.sort();
  return `%${tokens.join("%")}${tokens.length > 0 ? "%" : ""}`;
}

/**
 * Resolve a selection to the species codes the census actually holds.
 *
 * A clade code never appears in the census, so a clade takes its state down to
 * its leaves. An explicit leaf wins over the clade above it.
 */
export function leafStates(
  states: Map<string, TriState>,
  roots: PhyleticNode[],
): Map<string, TriState> {
  const leaves = new Map<string, TriState>();

  function walk(node: PhyleticNode, inherited: TriState): void {
    const own = states.get(node.code) ?? inherited;
    if (node.children.length === 0) {
      if (own !== "unconstrained") leaves.set(node.code, own);
      return;
    }
    for (const child of node.children) walk(child, own);
  }

  for (const root of roots) walk(root, "unconstrained");
  return leaves;
}

export function decodeProfilePattern(pattern: string): Map<string, TriState> {
  const states = new Map<string, TriState>();
  for (const token of pattern.split("%")) {
    const match = token.trim().match(/^([a-z]+):([YN])$/);
    if (match == null) continue;
    const [, code, state] = match;
    if (code == null) continue;
    states.set(code, state === "Y" ? "include" : "exclude");
  }
  return states;
}

// ---------------------------------------------------------------------------
// Species lists
// ---------------------------------------------------------------------------

/** The literal the reference client decodes as the empty set. */
const NO_SPECIES = "n/a";

/**
 * The two documentation parameters, in the shape the reference client reads
 * back when it reopens a step: vocabulary terms rather than display labels.
 */
export function buildSpeciesLists(states: Map<string, TriState>): {
  included: string;
  excluded: string;
} {
  const included: string[] = [];
  const excluded: string[] = [];
  for (const [code, state] of states) {
    if (state === "include") included.push(code);
    else if (state === "exclude") excluded.push(code);
  }
  return {
    included: included.length > 0 ? included.join(", ") : NO_SPECIES,
    excluded: excluded.length > 0 ? excluded.join(", ") : NO_SPECIES,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function nextTriState(current: TriState): TriState {
  if (current === "unconstrained") return "include";
  if (current === "include") return "exclude";
  return "unconstrained";
}

export function triStateIcon(state: TriState): string {
  if (state === "include") return "\u2713";
  if (state === "exclude") return "\u2717";
  return "\u25CB";
}

export function triStateColor(state: TriState): string {
  if (state === "include") return "text-green-500";
  if (state === "exclude") return "text-red-500";
  return "text-muted-foreground";
}

/** Collect all codes from a tree */
export function collectCodes(nodes: PhyleticNode[]): string[] {
  const codes: string[] = [];
  for (const node of nodes) {
    codes.push(node.code);
    codes.push(...collectCodes(node.children));
  }
  return codes;
}

/** Check if a node or any descendant matches the search query */
export function nodeMatchesSearch(node: PhyleticNode, query: string): boolean {
  if (node.label.toLowerCase().includes(query)) return true;
  return node.children.some((child) => nodeMatchesSearch(child, query));
}

/** Default expanded depth: top 2 levels */
export function defaultExpanded(nodes: PhyleticNode[], maxDepth: number): Set<string> {
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
