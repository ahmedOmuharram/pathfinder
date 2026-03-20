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
    if (includeMatch != null) {
      const code = includeMatch[1];
      if (code != null) states.set(code, "include");
      continue;
    }
    const excludeMatch = trimmed.match(/^([^>=]+)=0T$/);
    if (excludeMatch != null) {
      const code = excludeMatch[1];
      if (code != null) states.set(code, "exclude");
      continue;
    }
  }
  return states;
}

// ---------------------------------------------------------------------------
// Species lists
// ---------------------------------------------------------------------------

export function buildSpeciesLists(
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

/** Build code->label map from tree */
export function buildCodeToLabel(nodes: PhyleticNode[]): Map<string, string> {
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
