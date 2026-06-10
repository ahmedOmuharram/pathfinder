"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import { AlertCircle, Check, X } from "lucide-react";
import type { ResolvedGene } from "@pathfinder/shared";

export type ChipStatus = "pending" | "verified" | "invalid";

interface GeneChipProps {
  geneId: string;
  status: ChipStatus;
  resolvedGene?: ResolvedGene | null;
  onRemove: (geneId: string) => void;
}

const statusIcon: Record<ChipStatus, React.ReactNode> = {
  pending: null,
  verified: <Check className="h-2.5 w-2.5 text-success" />,
  invalid: <AlertCircle className="h-2.5 w-2.5 text-destructive" />,
};

const statusClasses: Record<ChipStatus, string> = {
  pending: "bg-muted text-muted-foreground border-border",
  verified: "bg-success/10 text-success border-success/30",
  invalid: "bg-destructive/10 text-destructive border-destructive/30",
};

function GeneHoverCard({
  gene,
  pos,
}: {
  gene: ResolvedGene;
  pos: { top: number; left: number };
}) {
  return createPortal(
    <div
      className="fixed z-50 w-64 rounded-md border border-border bg-popover p-2.5 shadow-lg text-xs"
      style={{ top: pos.top, left: pos.left }}
    >
      <div className="font-semibold text-foreground">{gene.displayName}</div>
      {gene.product !== "" && (
        <div className="mt-0.5 text-muted-foreground">{gene.product}</div>
      )}
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-muted-foreground">
        {gene.organism !== "" && <span>{gene.organism}</span>}
        {gene.geneType !== "" && <span>{gene.geneType}</span>}
        {gene.location !== "" && <span>{gene.location}</span>}
      </div>
    </div>,
    document.body,
  );
}

export function GeneChip({ geneId, status, resolvedGene, onRemove }: GeneChipProps) {
  const [hoverPos, setHoverPos] = useState<{ top: number; left: number } | null>(null);

  return (
    <>
      <span
        data-gene-chip
        data-status={status}
        onMouseEnter={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          setHoverPos({ top: rect.bottom + 4, left: rect.left });
        }}
        onMouseLeave={() => setHoverPos(null)}
        className={`animate-chip-in inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] leading-tight ${statusClasses[status]}`}
      >
        {statusIcon[status]}
        <span className="truncate max-w-[120px]">{geneId}</span>
        <button
          type="button"
          onClick={() => onRemove(geneId)}
          className="ml-0.5 rounded-full p-0.5 hover:bg-muted-foreground/20"
          aria-label={`Remove ${geneId}`}
        >
          <X className="h-2.5 w-2.5" />
        </button>
      </span>
      {hoverPos !== null && resolvedGene != null && (
        <GeneHoverCard gene={resolvedGene} pos={hoverPos} />
      )}
    </>
  );
}
