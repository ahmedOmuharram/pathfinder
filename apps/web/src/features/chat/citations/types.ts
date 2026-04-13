/**
 * Types for per-message citation numbering.
 *
 * Backend emits `source-url` parts (via `ToolReturn.metadata=[SourceUrlChunk(...)]`).
 * At the MessageBubble level we collect them into a numbering map, expose it
 * via React context so `TextPart`'s remark plugin can resolve `[@sourceId]`
 * tokens into numbered superscripts, and render a numbered Sources footer.
 */

export interface CitationEntry {
  /** Stable id emitted by the backend (matches `SourceUrlChunk.source_id`). */
  sourceId: string;
  url: string;
  title: string | undefined;
  /** 1-based position in the order sources appear on the message. */
  number: number;
}

export interface CitationIndex {
  entries: readonly CitationEntry[];
  /** Maps a sourceId tag → its 1-based citation number. */
  bySourceId: ReadonlyMap<string, number>;
}
