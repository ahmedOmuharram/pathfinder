import { useMemo } from "react";
import { AlertTriangle, Info } from "lucide-react";

const MIN_CONTROLS_WARN = 10;
const IMBALANCE_RATIO = 3;

interface ControlsStepProps {
  siteId: string;
  positiveGenes: { geneId: string }[];
  onPositiveGenesChange: (genes: { geneId: string }[]) => void;
  negativeGenes: { geneId: string }[];
  onNegativeGenesChange: (genes: { geneId: string }[]) => void;
  showGeneLookup: boolean;
  onShowGeneLookupChange: (val: boolean) => void;
  isTransformSearch: boolean;
  selectedSearch: string;
  selectedRecordType: string;
}

export function ControlsStep({
  positiveGenes,
  onPositiveGenesChange,
  negativeGenes,
  onNegativeGenesChange,
  isTransformSearch,
}: ControlsStepProps) {
  const warnings = useMemo(() => {
    const w: string[] = [];
    const posCount = positiveGenes.length;
    const negCount = negativeGenes.length;

    if (posCount > 0 && posCount < MIN_CONTROLS_WARN) {
      w.push(
        `Only ${posCount} positive control${posCount === 1 ? "" : "s"} — consider adding at least ${MIN_CONTROLS_WARN} for statistically meaningful results.`,
      );
    }
    if (negCount > 0 && negCount < MIN_CONTROLS_WARN) {
      w.push(
        `Only ${negCount} negative control${negCount === 1 ? "" : "s"} — consider adding at least ${MIN_CONTROLS_WARN} for statistically meaningful results.`,
      );
    }
    if (posCount > 0 && negCount > 0) {
      const ratio = Math.max(posCount, negCount) / Math.min(posCount, negCount);
      if (ratio > IMBALANCE_RATIO) {
        w.push(
          `Control sets are heavily imbalanced (${posCount} positive vs ${negCount} negative). Consider balancing them for more reliable metrics.`,
        );
      }
    }
    return w;
  }, [positiveGenes.length, negativeGenes.length]);

  return (
    <div className="space-y-4">
      {isTransformSearch && (
        <div className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50/80 p-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          <p className="text-[11px] text-amber-700 leading-relaxed">
            The selected search is a <span className="font-semibold">transform</span>{" "}
            that requires input from another step. Control evaluation may produce
            incomplete results when run in isolation.
          </p>
        </div>
      )}

      <div>
        <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Positive Controls (genes that SHOULD be found)
        </label>
        <textarea
          value={positiveGenes.map((g) => g.geneId).join("\n")}
          onChange={(e) => {
            const ids = e.target.value
              .split(/[\n,]/)
              .map((s) => s.trim())
              .filter(Boolean);
            onPositiveGenesChange(ids.map((id) => ({ geneId: id })));
          }}
          placeholder="Enter gene IDs, one per line..."
          className="w-full rounded-md border border-slate-200 px-3 py-2 text-[12px] outline-none placeholder:text-slate-400 focus:border-slate-300"
          rows={4}
        />
        <div className="mt-0.5 text-[10px] text-slate-400">
          {positiveGenes.length} gene{positiveGenes.length !== 1 ? "s" : ""}
        </div>
      </div>

      <div>
        <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Negative Controls (genes that should NOT be found)
        </label>
        <textarea
          value={negativeGenes.map((g) => g.geneId).join("\n")}
          onChange={(e) => {
            const ids = e.target.value
              .split(/[\n,]/)
              .map((s) => s.trim())
              .filter(Boolean);
            onNegativeGenesChange(ids.map((id) => ({ geneId: id })));
          }}
          placeholder="Enter gene IDs, one per line..."
          className="w-full rounded-md border border-slate-200 px-3 py-2 text-[12px] outline-none placeholder:text-slate-400 focus:border-slate-300"
          rows={4}
        />
        <div className="mt-0.5 text-[10px] text-slate-400">
          {negativeGenes.length} gene{negativeGenes.length !== 1 ? "s" : ""}
        </div>
      </div>

      {warnings.length > 0 && (
        <div className="rounded-lg border border-blue-200 bg-blue-50/60 p-3 space-y-1.5">
          {warnings.map((w) => (
            <div key={w} className="flex items-start gap-2">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-blue-500" />
              <p className="text-[11px] text-blue-700">{w}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
