import { useState, useMemo } from "react";
import type { EnrichmentResult, EnrichmentTerm } from "@pathfinder/shared";
import { ArrowUpDown } from "lucide-react";
import { Section } from "./Section";

type SortKey = "termName" | "geneCount" | "foldEnrichment" | "pValue" | "fdr";
type SortDir = "asc" | "desc";

interface EnrichmentSectionProps {
  results: EnrichmentResult[];
}

const analysisLabels: Record<string, string> = {
  go_function: "GO: Molecular Function",
  go_component: "GO: Cellular Component",
  go_process: "GO: Biological Process",
  pathway: "Metabolic Pathway",
  word: "Word Enrichment",
};

export function EnrichmentSection({ results }: EnrichmentSectionProps) {
  const [activeTab, setActiveTab] = useState(0);
  const [pThreshold, setPThreshold] = useState(0.05);

  return (
    <Section title="Enrichment Analysis">
      <div className="rounded-lg border border-border bg-card">
        <div className="flex items-center gap-0 border-b border-border px-4">
          {results.map((r, i) => {
            const count = r.terms.filter((t) => t.pValue <= pThreshold).length;
            return (
              <button
                key={r.analysisType}
                type="button"
                onClick={() => setActiveTab(i)}
                className={`relative px-3 py-2.5 text-xs font-medium transition ${
                  activeTab === i
                    ? "text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {analysisLabels[r.analysisType] ?? r.analysisType}
                <span className="ml-1 text-xs text-muted-foreground">{count}</span>
                {activeTab === i && (
                  <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-primary" />
                )}
              </button>
            );
          })}
          <div className="ml-auto flex items-center gap-2 py-2">
            <label className="text-xs text-muted-foreground">p &le;</label>
            <select
              value={pThreshold}
              onChange={(e) => setPThreshold(parseFloat(e.target.value))}
              className="rounded border border-border bg-card px-2 py-1 text-xs text-muted-foreground outline-none transition-colors duration-150"
            >
              <option value={0.001}>0.001</option>
              <option value={0.01}>0.01</option>
              <option value={0.05}>0.05</option>
              <option value={0.1}>0.1</option>
              <option value={1}>All</option>
            </select>
          </div>
        </div>

        {results[activeTab] && (
          <EnrichmentTable
            terms={results[activeTab].terms.filter((t) => t.pValue <= pThreshold)}
          />
        )}
      </div>
    </Section>
  );
}

function EnrichmentTable({ terms }: { terms: EnrichmentTerm[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("pValue");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const sorted = useMemo(() => {
    const copy = [...terms];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "number" && typeof bv === "number") {
        return sortDir === "asc" ? av - bv : bv - av;
      }
      return sortDir === "asc"
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av));
    });
    return copy;
  }, [terms, sortKey, sortDir]);

  const toggle = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(key === "termName" ? "asc" : "asc");
    }
  };

  if (terms.length === 0) {
    return (
      <div className="px-5 py-8 text-center text-xs text-muted-foreground">
        No enriched terms at this threshold.
      </div>
    );
  }

  const columns: { key: SortKey; label: string; align?: string }[] = [
    { key: "termName", label: "Term" },
    { key: "geneCount", label: "Genes", align: "text-right" },
    { key: "foldEnrichment", label: "Fold", align: "text-right" },
    { key: "pValue", label: "p-value", align: "text-right" },
    { key: "fdr", label: "FDR", align: "text-right" },
  ];

  return (
    <div className="max-h-72 overflow-y-auto">
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-card">
          <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`cursor-pointer select-none px-4 py-2.5 font-medium transition-colors duration-150 ${col.align ?? ""}`}
                onClick={() => toggle(col.key)}
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  <ArrowUpDown className="h-2.5 w-2.5" />
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border/50">
          {sorted.map((t) => (
            <tr key={t.termId} className="transition hover:bg-accent">
              <td className="max-w-xs truncate px-4 py-2 text-foreground">
                <span className="mr-1.5 font-mono text-xs text-muted-foreground">
                  {t.termId}
                </span>
                {t.termName}
              </td>
              <td className="px-4 py-2 text-right font-mono tabular-nums text-muted-foreground">
                {t.geneCount}
              </td>
              <td className="px-4 py-2 text-right font-mono tabular-nums text-muted-foreground">
                {t.foldEnrichment.toFixed(2)}
              </td>
              <td className="px-4 py-2 text-right font-mono tabular-nums text-muted-foreground">
                {t.pValue.toExponential(2)}
              </td>
              <td className="px-4 py-2 text-right font-mono tabular-nums text-muted-foreground">
                {t.fdr.toExponential(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
