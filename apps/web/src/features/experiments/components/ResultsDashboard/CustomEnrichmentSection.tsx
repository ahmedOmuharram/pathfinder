import { useState, useCallback } from "react";
import { Play, Loader2 } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { Badge } from "@/lib/components/ui/Badge";
import { runCustomEnrichment, type CustomEnrichmentResult } from "../../api";

interface CustomEnrichmentSectionProps {
  experimentId: string;
}

export function CustomEnrichmentSection({
  experimentId,
}: CustomEnrichmentSectionProps) {
  const [geneSetName, setGeneSetName] = useState("");
  const [geneIdsText, setGeneIdsText] = useState("");
  const [results, setResults] = useState<CustomEnrichmentResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleTest = useCallback(async () => {
    const ids = geneIdsText
      .split(/[\n,\t]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (ids.length === 0 || !geneSetName.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const result = await runCustomEnrichment(experimentId, geneSetName.trim(), ids);
      setResults((prev) => [result, ...prev]);
      setGeneSetName("");
      setGeneIdsText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
    setLoading(false);
  }, [experimentId, geneSetName, geneIdsText]);

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Test if results are enriched for your own gene sets using Fisher&apos;s exact
        test.
      </p>

      <div className="space-y-3">
        <input
          type="text"
          value={geneSetName}
          onChange={(e) => setGeneSetName(e.target.value)}
          placeholder="Gene set name (e.g. ISG response genes)"
          className="h-8 w-full rounded-md border border-input bg-background px-3 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <textarea
          value={geneIdsText}
          onChange={(e) => setGeneIdsText(e.target.value)}
          placeholder="Paste gene IDs (one per line, comma, or tab separated)"
          rows={3}
          className="w-full resize-none rounded-md border border-input bg-background px-3 py-2 text-xs font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <Button
          size="sm"
          onClick={handleTest}
          disabled={loading || !geneSetName.trim() || !geneIdsText.trim()}
          loading={loading}
        >
          <Play className="h-3.5 w-3.5" />
          Run Fisher&apos;s Exact Test
        </Button>
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {results.length > 0 && (
        <div className="space-y-2">
          {results.map((r, i) => (
            <div key={i} className="rounded-lg border border-border bg-card p-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-foreground">
                  {r.geneSetName}
                </span>
                <Badge
                  variant={r.pValue < 0.05 ? "default" : "secondary"}
                  className="font-mono text-xs"
                >
                  p ={" "}
                  {r.pValue < 0.001 ? r.pValue.toExponential(2) : r.pValue.toFixed(4)}
                </Badge>
              </div>
              <div className="mt-1.5 flex gap-4 text-xs text-muted-foreground">
                <span>
                  Overlap: {r.overlapCount} / {r.tpCount} TP genes
                </span>
                <span>Fold: {r.foldEnrichment.toFixed(2)}x</span>
                <span>Gene set size: {r.geneSetSize}</span>
              </div>
              {r.overlapGenes.length > 0 && (
                <div className="mt-1.5 truncate text-xs font-mono text-muted-foreground/60">
                  {r.overlapGenes.slice(0, 20).join(", ")}
                  {r.overlapGenes.length > 20 && ` +${r.overlapGenes.length - 20} more`}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
