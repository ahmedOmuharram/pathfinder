import { useMemo } from "react";
import { AlertTriangle, Search as SearchIcon } from "lucide-react";
import { GeneLookupPanel } from "../GeneLookupPanel";
import { ValidatedGeneInput } from "../ValidatedGeneInput";
import type { ResolvedGene } from "@/lib/api/client";

interface ControlsStepProps {
  siteId: string;
  positiveGenes: ResolvedGene[];
  onPositiveGenesChange: (genes: ResolvedGene[]) => void;
  negativeGenes: ResolvedGene[];
  onNegativeGenesChange: (genes: ResolvedGene[]) => void;
  showGeneLookup: boolean;
  onShowGeneLookupChange: (val: boolean) => void;
  isTransformSearch: boolean;
}

export function ControlsStep({
  siteId,
  positiveGenes,
  onPositiveGenesChange,
  negativeGenes,
  onNegativeGenesChange,
  showGeneLookup,
  onShowGeneLookupChange,
  isTransformSearch,
}: ControlsStepProps) {
  const positiveGeneIds = useMemo(
    () => new Set(positiveGenes.map((g) => g.geneId)),
    [positiveGenes],
  );
  const negativeGeneIds = useMemo(
    () => new Set(negativeGenes.map((g) => g.geneId)),
    [negativeGenes],
  );

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

      {!showGeneLookup ? (
        <button
          type="button"
          onClick={() => onShowGeneLookupChange(true)}
          className="flex w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-indigo-300 bg-indigo-50/50 px-3 py-2.5 text-[11px] font-medium text-indigo-600 transition hover:bg-indigo-50"
        >
          <SearchIcon className="h-3.5 w-3.5" />
          Find Gene IDs via Site Search
        </button>
      ) : (
        <GeneLookupPanel
          siteId={siteId}
          positiveGeneIds={positiveGeneIds}
          negativeGeneIds={negativeGeneIds}
          onAddPositive={(gene) => onPositiveGenesChange([...positiveGenes, gene])}
          onAddNegative={(gene) => onNegativeGenesChange([...negativeGenes, gene])}
          onClose={() => onShowGeneLookupChange(false)}
        />
      )}

      <ValidatedGeneInput
        siteId={siteId}
        genes={positiveGenes}
        onGenesChange={onPositiveGenesChange}
        excludeGeneIds={negativeGeneIds}
        label="Positive Controls (known genes that SHOULD be found)"
        placeholder="Type a gene ID and press Enter…"
        variant="positive"
      />

      <ValidatedGeneInput
        siteId={siteId}
        genes={negativeGenes}
        onGenesChange={onNegativeGenesChange}
        excludeGeneIds={positiveGeneIds}
        label="Negative Controls (known genes that should NOT be found)"
        placeholder="Type a gene ID and press Enter…"
        variant="negative"
      />
    </div>
  );
}
