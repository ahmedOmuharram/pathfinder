import { useState, useCallback } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { runCustomEnrichment, type CustomEnrichmentResult } from "../../api";
import { Section } from "./Section";

interface CustomEnrichmentSectionProps {
  experimentId: string;
}

export function CustomEnrichmentSection({
  experimentId,
}: CustomEnrichmentSectionProps) {
  const [expanded, setExpanded] = useState(false);
  const [geneSetName, setGeneSetName] = useState("");
  const [geneIdsText, setGeneIdsText] = useState("");
  const [results, setResults] = useState<CustomEnrichmentResult[]>([]);
  const [loading, setLoading] = useState(false);

  const handleTest = useCallback(async () => {
    const ids = geneIdsText
      .split(/[\n,\t]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (ids.length === 0 || !geneSetName.trim()) return;

    setLoading(true);
    try {
      const result = await runCustomEnrichment(experimentId, geneSetName.trim(), ids);
      setResults((prev) => [result, ...prev]);
      setGeneSetName("");
      setGeneIdsText("");
    } catch {
      /* ignore */
    }
    setLoading(false);
  }, [experimentId, geneSetName, geneIdsText]);

  return (
    <Section title="Custom Gene Set Enrichment">
      <div className="rounded-lg border border-slate-200 bg-white">
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
          <span className="text-xs text-slate-600">
            Test if results are enriched for your own gene sets
          </span>
        </button>
        {expanded && (
          <div className="space-y-3 border-t border-slate-200 px-5 py-4">
            <input
              type="text"
              value={geneSetName}
              onChange={(e) => setGeneSetName(e.target.value)}
              placeholder="Gene set name (e.g. ISG response genes)"
              className="w-full rounded-md border border-slate-200 px-3 py-1.5 text-xs outline-none placeholder:text-slate-400 focus:border-slate-300"
            />
            <textarea
              value={geneIdsText}
              onChange={(e) => setGeneIdsText(e.target.value)}
              placeholder="Paste gene IDs (one per line, comma, or tab separated)"
              rows={4}
              className="w-full resize-none rounded-md border border-slate-200 px-3 py-2 text-xs font-mono outline-none placeholder:text-slate-400 focus:border-slate-300"
            />
            <button
              type="button"
              onClick={handleTest}
              disabled={loading || !geneSetName.trim() || !geneIdsText.trim()}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-800 disabled:opacity-50"
            >
              {loading ? "Testing..." : "Run Fisher\u2019s Exact Test"}
            </button>

            {results.length > 0 && (
              <div className="mt-3 space-y-2">
                {results.map((r, i) => (
                  <div key={i} className="rounded-md border border-slate-200 p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-slate-800">
                        {r.geneSetName}
                      </span>
                      <span
                        className={`text-xs font-mono ${r.pValue < 0.05 ? "font-semibold text-slate-900" : "text-slate-500"}`}
                      >
                        p ={" "}
                        {r.pValue < 0.001
                          ? r.pValue.toExponential(2)
                          : r.pValue.toFixed(4)}
                      </span>
                    </div>
                    <div className="mt-1 flex gap-4 text-[10px] text-slate-500">
                      <span>
                        Overlap: {r.overlapCount} / {r.tpCount} TP genes
                      </span>
                      <span>Fold: {r.foldEnrichment.toFixed(2)}x</span>
                      <span>Gene set size: {r.geneSetSize}</span>
                    </div>
                    {r.overlapGenes.length > 0 && (
                      <div className="mt-1.5 truncate text-[10px] font-mono text-slate-400">
                        {r.overlapGenes.slice(0, 20).join(", ")}
                        {r.overlapGenes.length > 20 &&
                          ` +${r.overlapGenes.length - 20} more`}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Section>
  );
}
