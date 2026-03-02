import type { GeneSearchResult, ResolvedGene } from "@pathfinder/shared";
import { Check, ChevronDown, ChevronUp, Minus, Plus } from "lucide-react";

export function toResolvedGene(g: GeneSearchResult): ResolvedGene {
  return {
    geneId: g.geneId,
    displayName: g.displayName,
    organism: g.organism,
    product: g.product,
    geneName: g.geneName ?? "",
    geneType: g.geneType ?? "",
    location: g.location ?? "",
  };
}

interface GeneResultRowProps {
  gene: GeneSearchResult;
  isExpanded: boolean;
  onToggleExpand: (geneId: string) => void;
  positiveGeneIds: Set<string>;
  negativeGeneIds: Set<string>;
  onAddPositive: (gene: ResolvedGene) => void;
  onAddNegative: (gene: ResolvedGene) => void;
}

export function GeneResultRow({
  gene,
  isExpanded,
  onToggleExpand,
  positiveGeneIds,
  negativeGeneIds,
  onAddPositive,
  onAddNegative,
}: GeneResultRowProps) {
  const isPos = positiveGeneIds.has(gene.geneId);
  const isNeg = negativeGeneIds.has(gene.geneId);
  const assigned = isPos || isNeg;

  return (
    <div className="border-b border-border/50 last:border-b-0">
      <div className="flex items-center gap-2 px-3 py-2">
        <button
          type="button"
          onClick={() => onToggleExpand(gene.geneId)}
          className="shrink-0 rounded p-0.5 text-muted-foreground hover:bg-muted"
        >
          {isExpanded ? (
            <ChevronUp className="h-3 w-3" />
          ) : (
            <ChevronDown className="h-3 w-3" />
          )}
        </button>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-xs font-semibold text-foreground">
              {gene.geneId}
            </span>
            {gene.organism && (
              <span className="truncate text-xs text-muted-foreground">
                {gene.organism}
              </span>
            )}
          </div>
          {gene.displayName && gene.displayName !== gene.geneId && (
            <div className="truncate text-xs text-muted-foreground">
              {gene.displayName}
            </div>
          )}
        </div>

        <div className="flex shrink-0 gap-1">
          {isPos ? (
            <span className="flex items-center gap-0.5 rounded border border-emerald-300 bg-emerald-100 px-1.5 py-0.5 text-xs font-medium text-success">
              <Check className="h-2.5 w-2.5" />
              Pos
            </span>
          ) : (
            <button
              type="button"
              disabled={assigned}
              onClick={() => onAddPositive(toResolvedGene(gene))}
              title={
                isNeg ? "Already in Negative Controls" : "Add to Positive Controls"
              }
              className="flex items-center gap-0.5 rounded border border-emerald-200 bg-success/10 px-1.5 py-0.5 text-xs font-medium text-success transition hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Plus className="h-2.5 w-2.5" />
              Pos
            </button>
          )}
          {isNeg ? (
            <span className="flex items-center gap-0.5 rounded border border-red-300 bg-red-100 px-1.5 py-0.5 text-xs font-medium text-destructive">
              <Check className="h-2.5 w-2.5" />
              Neg
            </span>
          ) : (
            <button
              type="button"
              disabled={assigned}
              onClick={() => onAddNegative(toResolvedGene(gene))}
              title={
                isPos ? "Already in Positive Controls" : "Add to Negative Controls"
              }
              className="flex items-center gap-0.5 rounded border border-destructive/30 bg-destructive/5 px-1.5 py-0.5 text-xs font-medium text-destructive transition hover:bg-destructive/10 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Minus className="h-2.5 w-2.5" />
              Neg
            </button>
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="space-y-0.5 bg-muted px-3 py-2 pl-9 text-xs text-muted-foreground">
          {gene.product && (
            <div>
              <span className="font-medium text-muted-foreground">Product: </span>
              {gene.product}
            </div>
          )}
          {gene.organism && (
            <div>
              <span className="font-medium text-muted-foreground">Organism: </span>
              {gene.organism}
            </div>
          )}
          {gene.matchedFields.length > 0 && (
            <div>
              <span className="font-medium text-muted-foreground">Matched in: </span>
              {gene.matchedFields.join(", ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
