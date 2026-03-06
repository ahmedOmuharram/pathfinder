"use client";

import { useState, useCallback } from "react";
import { Dna, Play, Loader2 } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { EnrichmentSection } from "@/features/analysis";
import type { EnrichmentResult } from "@pathfinder/shared";
import { AnalysisPanelContainer } from "../AnalysisPanelContainer";
import { useWorkbenchStore } from "../../store";
import { enrichGeneSet } from "../../api/geneSets";

// ---------------------------------------------------------------------------
// Enrichment type chips
// ---------------------------------------------------------------------------

const ENRICHMENT_TYPES = [
  { key: "go_process", label: "GO:BP" },
  { key: "go_function", label: "GO:MF" },
  { key: "go_component", label: "GO:CC" },
  { key: "pathway", label: "Pathway" },
  { key: "word", label: "Word" },
] as const;

type EnrichmentTypeKey = (typeof ENRICHMENT_TYPES)[number]["key"];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EnrichmentPanel() {
  const geneSets = useWorkbenchStore((s) => s.geneSets);
  const activeSetId = useWorkbenchStore((s) => s.activeSetId);
  const activeSet = geneSets.find((gs) => gs.id === activeSetId);

  const [selectedTypes, setSelectedTypes] = useState<Set<EnrichmentTypeKey>>(
    new Set(ENRICHMENT_TYPES.map((t) => t.key)),
  );
  const [results, setResults] = useState<EnrichmentResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleType = useCallback((key: EnrichmentTypeKey) => {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const handleRun = useCallback(async () => {
    if (!activeSet || selectedTypes.size === 0) return;
    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const results = await enrichGeneSet(activeSet.id, [...selectedTypes]);
      setResults(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [activeSet, selectedTypes]);

  return (
    <AnalysisPanelContainer
      panelId="enrichment"
      title="Enrichment Analysis"
      subtitle="GO terms, pathways, and word enrichment"
      icon={<Dna className="h-4 w-4" />}
    >
      <div className="space-y-4">
        {/* Type selector chips */}
        <div className="flex flex-wrap items-center gap-2">
          {ENRICHMENT_TYPES.map(({ key, label }) => {
            const active = selectedTypes.has(key);
            return (
              <button
                key={key}
                type="button"
                onClick={() => toggleType(key)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                  active
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-card text-muted-foreground hover:border-primary/40"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* Run button */}
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            onClick={handleRun}
            disabled={loading || selectedTypes.size === 0}
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
            {loading ? "Running..." : "Run Enrichment"}
          </Button>
          {loading && (
            <span className="text-xs text-muted-foreground">
              Analyzing {selectedTypes.size} enrichment type
              {selectedTypes.size !== 1 ? "s" : ""}...
            </span>
          )}
        </div>

        {error && <p className="text-xs text-destructive">{error}</p>}

        {/* Results */}
        {results && results.length > 0 && <EnrichmentSection results={results} />}

        {results && results.length === 0 && (
          <p className="py-4 text-center text-xs text-muted-foreground">
            No enrichment results returned. Try different enrichment types.
          </p>
        )}
      </div>
    </AnalysisPanelContainer>
  );
}
