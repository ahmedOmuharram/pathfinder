import { ChevronDown, ChevronUp } from "lucide-react";
import type { Message } from "@pathfinder/shared";
import { Card } from "@/lib/components/ui/Card";

interface SourcesPartProps {
  messageKey: string;
  citations: NonNullable<Message["citations"]>;
  expandedSources: Record<string, boolean>;
  setExpandedSources: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  showCitationTags: boolean;
  setShowCitationTags: React.Dispatch<React.SetStateAction<boolean>>;
}

export function SourcesPart({
  messageKey,
  citations,
  expandedSources,
  setExpandedSources,
  showCitationTags,
  setShowCitationTags,
}: SourcesPartProps) {
  const total = citations.length;
  const expanded = Boolean(expandedSources[messageKey]);

  return (
    <Card className="rounded-md px-2 py-2 text-sm">
      <div className="mb-1 flex items-center justify-between gap-2">
        <div className="font-medium text-foreground">Sources</div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className={`rounded-md border px-2 py-1 text-xs transition-colors ${
              showCitationTags
                ? "border-input bg-accent text-foreground"
                : "border-border bg-card text-foreground hover:bg-accent"
            }`}
            onClick={() => setShowCitationTags((v) => !v)}
            aria-pressed={showCitationTags}
            title="Toggle citation tags"
          >
            {showCitationTags ? "Hide citation tags" : "Show citation tags"}
          </button>
          <button
            type="button"
            className="inline-flex items-center justify-center rounded-md border border-border bg-card p-1 text-foreground transition-colors duration-150 hover:bg-accent"
            onClick={() =>
              setExpandedSources((prev) => ({
                ...prev,
                [messageKey]: !expanded,
              }))
            }
            aria-label={expanded ? "Collapse sources" : "Expand sources"}
            title={expanded ? "Collapse sources" : "Expand sources"}
          >
            {expanded ? (
              <ChevronUp className="h-4 w-4" aria-hidden="true" />
            ) : (
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      {!expanded ? (
        <div className="text-xs text-muted-foreground">
          {total} source{total === 1 ? "" : "s"}
        </div>
      ) : (
        <ol className="list-decimal space-y-1 pl-4">
          {citations.map((c, i) => (
            <li key={c.id} id={`cite-${i + 1}`}>
              {showCitationTags && c.tag != null && c.tag !== "" ? (
                <span className="mr-2 font-mono text-xs text-muted-foreground">
                  [{c.tag}]{" "}
                </span>
              ) : null}
              {Array.isArray(c.authors) && c.authors.length > 0 ? (
                <span className="text-muted-foreground">
                  {`${c.authors.filter(Boolean).join(", ")} `}
                </span>
              ) : null}
              {c.url != null && c.url !== "" ? (
                <a
                  href={c.url}
                  target="_blank"
                  rel="noreferrer"
                  className="underline decoration-muted-foreground/40 underline-offset-2 hover:decoration-muted-foreground"
                >
                  {c.title}
                </a>
              ) : (
                <span>{c.title}</span>
              )}
              {c.year != null ? (
                <span className="text-muted-foreground"> ({c.year})</span>
              ) : null}
              {c.doi != null && c.doi !== "" ? (
                <span className="text-muted-foreground"> · DOI: {c.doi}</span>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
