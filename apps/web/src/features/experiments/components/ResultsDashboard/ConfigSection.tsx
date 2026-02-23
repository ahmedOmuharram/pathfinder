import { useState } from "react";
import type { Experiment } from "@pathfinder/shared";
import { ChevronDown, ChevronRight } from "lucide-react";

interface ConfigSectionProps {
  experiment: Experiment;
}

export function ConfigSection({ experiment }: ConfigSectionProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-5 py-3 text-left transition hover:bg-slate-50/80"
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
        )}
        <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">
          Experiment Configuration
        </span>
      </button>
      {expanded && (
        <div className="border-t border-slate-200 px-5 py-4">
          <pre className="max-h-56 overflow-auto rounded-md bg-slate-50 p-4 font-mono text-[11px] leading-relaxed text-slate-600">
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
