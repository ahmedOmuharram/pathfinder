import { useState } from "react";
import type { Experiment, GeneInfo } from "@pathfinder/shared";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Section } from "./Section";

interface GeneListsSectionProps {
  experiment: Experiment;
}

export function GeneListsSection({ experiment }: GeneListsSectionProps) {
  const lists = [
    { label: "True Positives", genes: experiment.truePositiveGenes },
    { label: "False Negatives", genes: experiment.falseNegativeGenes },
    { label: "False Positives", genes: experiment.falsePositiveGenes },
    { label: "True Negatives", genes: experiment.trueNegativeGenes },
  ];

  return (
    <Section title="Gene Lists">
      <div className="rounded-lg border border-slate-200 bg-white divide-y divide-slate-100">
        {lists.map((list) => (
          <GeneListRow key={list.label} label={list.label} genes={list.genes} />
        ))}
      </div>
    </Section>
  );
}

function GeneListRow({ label, genes }: { label: string; genes: GeneInfo[] }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-5 py-2.5 text-left transition hover:bg-slate-50/80"
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-slate-400" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-400" />
        )}
        <span className="text-[13px] text-slate-700">{label}</span>
        <span className="ml-auto font-mono text-xs tabular-nums text-slate-400">
          {genes.length}
        </span>
      </button>
      {expanded && genes.length > 0 && (
        <div className="border-t border-slate-100 bg-slate-50/40 px-5 py-3">
          <div className="max-h-40 overflow-y-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-slate-400">
                  <th className="pb-1.5 pr-4 font-medium">ID</th>
                  <th className="pb-1.5 font-medium">Product</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {genes.slice(0, 100).map((g) => (
                  <tr key={g.id}>
                    <td className="py-1 pr-4 font-mono text-slate-700">{g.id}</td>
                    <td className="py-1 text-slate-500">{g.product ?? "\u2014"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {genes.length > 100 && (
              <div className="mt-2 text-[11px] text-slate-400">
                Showing 100 of {genes.length} genes
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
