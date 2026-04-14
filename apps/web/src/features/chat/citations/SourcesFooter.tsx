import { ExternalLink } from "lucide-react";

import {
  Source,
  Sources,
  SourcesContent,
  SourcesTrigger,
} from "@/components/ai-elements/sources";

import type { CitationEntry } from "./types";

export function SourcesFooter({
  entries,
}: {
  entries: readonly CitationEntry[];
}) {
  if (entries.length === 0) return null;
  return (
    <Sources
      defaultOpen
      data-testid="sources-footer"
      className="mt-2 border-t border-border/40 pt-2"
    >
      <SourcesTrigger count={entries.length} />
      <SourcesContent>
        {entries.map((entry) => (
          <Source
            key={entry.sourceId}
            id={`cite-${String(entry.number)}`}
            href={entry.url}
            title={entry.title ?? entry.url}
          >
            <span className="font-mono text-muted-foreground">
              {entry.number}.
            </span>
            <span className="text-foreground underline decoration-dotted underline-offset-2 hover:text-primary">
              {entry.title ?? entry.url}
            </span>
            <ExternalLink className="h-3 w-3 opacity-60" aria-hidden="true" />
          </Source>
        ))}
      </SourcesContent>
    </Sources>
  );
}
