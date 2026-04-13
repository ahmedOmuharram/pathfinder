/**
 * Derives a `CitationIndex` from a message's `source-url` parts.
 *
 * Numbering is 1-based and preserves the order sources appear in the message
 * parts array. Duplicate `sourceId`s reuse the first assigned number (the
 * remark plugin can then map repeated `[@tag]` tokens to the same footnote).
 */

import type { PathfinderUIMessage } from "@pathfinder/shared";

import type { CitationEntry, CitationIndex } from "./types";

const EMPTY_INDEX: CitationIndex = Object.freeze({
  entries: Object.freeze([]),
  bySourceId: new Map(),
});

export function buildCitationIndex(
  parts: PathfinderUIMessage["parts"],
): CitationIndex {
  const entries: CitationEntry[] = [];
  const bySourceId = new Map<string, number>();

  for (const part of parts) {
    if (part.type !== "source-url") continue;
    const sourceId = part.sourceId;
    if (bySourceId.has(sourceId)) continue;
    const number = entries.length + 1;
    bySourceId.set(sourceId, number);
    entries.push({
      sourceId,
      url: part.url,
      title: part.title ?? undefined,
      number,
    });
  }

  if (entries.length === 0) return EMPTY_INDEX;
  return { entries, bySourceId };
}
