import { useState } from "react";
import type { Experiment } from "@pathfinder/shared";
import { ChevronDown, ChevronRight } from "lucide-react";

interface ConfigSectionProps {
  experiment: Experiment;
}

export function ConfigSection({ experiment }: ConfigSectionProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <section className="rounded-lg border border-border bg-card">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-5 py-3 text-left transition hover:bg-accent"
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
        )}
        <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Experiment Configuration
        </span>
      </button>
      {expanded && (
        <div className="border-t border-border px-5 py-4">
          <pre className="max-h-56 overflow-auto rounded-md bg-muted p-4 font-mono text-xs leading-relaxed text-muted-foreground">
            {JSON.stringify(
              {
                ...experiment.config,
                parameters:
                  experiment.config.parameterDisplayValues ??
                  experiment.config.parameters,
              },
              null,
              2,
            )}
          </pre>
        </div>
      )}
    </section>
  );
}
