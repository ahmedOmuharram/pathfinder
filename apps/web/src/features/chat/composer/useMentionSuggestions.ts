"use client";

/**
 * Builds the candidate list for the composer's @-mention dropdown.
 *
 * Pulls from:
 *   - the active strategy and its steps (`useStrategyStore`)
 *   - gene sets for the selected site (`useGeneSetsQuery`)
 *
 * Filters by a case-insensitive substring match against each candidate's
 * display name and id. Returns a flat, ranked list: strategy → steps →
 * gene sets. The composer inserts the selected candidate as a plain-text
 * token `@{kind}:{id}` into the textarea; the backend agent resolves the
 * reference. There is no wire-format change: mentions are literally part of
 * the user's text.
 *
 * React Compiler (`babel-plugin-react-compiler`) handles the memoization
 * automatically; manual `useMemo` is banned in this codebase.
 */

import { useGeneSetsQuery } from "@/lib/query/hooks/useGeneSetsQuery";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/strategy/store";

export type MentionKind = "strategy" | "step" | "geneset";

export interface MentionCandidate {
  /** Stable wire id, used for the inserted `@{kind}:{id}` token. */
  id: string;
  /** Human-readable label shown in the dropdown. */
  label: string;
  /** Secondary line (e.g. search name, gene count). */
  sublabel: string | undefined;
  kind: MentionKind;
}

const MAX_RESULTS = 8;

export function useMentionSuggestions(query: string): MentionCandidate[] {
  const strategy = useStrategyStore((s) => s.strategy);
  const stepsById = useStrategyStore((s) => s.stepsById);
  const siteId = useSessionStore((s) => s.selectedSite);
  const { data: geneSets = [] } = useGeneSetsQuery(siteId);

  const q = query.trim().toLowerCase();
  const matches = (s: string): boolean => q.length === 0 || s.toLowerCase().includes(q);

  const candidates: MentionCandidate[] = [];

  if (strategy !== null) {
    const label = strategy.name.length > 0 ? strategy.name : `strategy ${strategy.id}`;
    if (matches(label) || matches(strategy.id)) {
      candidates.push({
        id: strategy.id,
        label,
        sublabel: "active strategy",
        kind: "strategy",
      });
    }
  }

  for (const step of Object.values(stepsById)) {
    const searchName = step.searchName;
    const label = step.displayName ?? searchName ?? step.id;
    if (!matches(label) && !matches(step.id) && !matches(searchName ?? "")) continue;
    candidates.push({
      id: step.id,
      label,
      sublabel: searchName ?? undefined,
      kind: "step",
    });
  }

  for (const geneSet of geneSets) {
    const label = geneSet.name;
    if (!matches(label) && !matches(geneSet.id)) continue;
    candidates.push({
      id: geneSet.id,
      label,
      sublabel: `${String(geneSet.geneCount)} genes`,
      kind: "geneset",
    });
  }

  return candidates.slice(0, MAX_RESULTS);
}

/** Formats a candidate as the inserted text token. */
export function formatMentionToken(candidate: MentionCandidate): string {
  return `@${candidate.kind}:${candidate.id}`;
}
