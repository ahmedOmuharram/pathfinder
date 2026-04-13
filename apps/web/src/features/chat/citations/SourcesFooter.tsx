/**
 * Numbered sources list rendered at the foot of an assistant message bubble.
 *
 * The ordered list's `<li>` ids (`cite-1`, `cite-2`, ...) are the anchor
 * targets of inline citation links produced by `createCitationRemarkPlugin`.
 */

import { ExternalLink } from "lucide-react";

import type { CitationEntry } from "./types";

export function SourcesFooter({
  entries,
}: {
  entries: readonly CitationEntry[];
}) {
  if (entries.length === 0) return null;
  return (
    <section
      className="mt-2 border-t border-border/40 pt-2"
      data-testid="sources-footer"
    >
      <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Sources
      </h4>
      <ol className="m-0 space-y-1 pl-5 text-xs">
        {entries.map((entry) => (
          <li
            key={entry.sourceId}
            id={`cite-${String(entry.number)}`}
            className="text-muted-foreground"
          >
            <a
              href={entry.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-foreground underline decoration-dotted underline-offset-2 hover:text-primary"
            >
              <span>{entry.title ?? entry.url}</span>
              <ExternalLink className="h-3 w-3 opacity-60" aria-hidden="true" />
            </a>
          </li>
        ))}
      </ol>
    </section>
  );
}
