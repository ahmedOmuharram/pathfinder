"use client";

import { useState, useRef } from "react";
import { createPortal } from "react-dom";
import { useHover } from "usehooks-ts";
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
  verified: <Check className="h-2.5 w-2.5 text-green-500" />,
  invalid: <AlertCircle className="h-2.5 w-2.5 text-red-400" />,
};

const statusClasses: Record<ChipStatus, string> = {
  pending: "bg-muted text-muted-foreground border-border",
  verified: "bg-green-500/10 text-green-700 dark:text-green-300 border-green-500/30",
  invalid: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/30",
};

function GeneHoverCard({ gene, pos }: { gene: ResolvedGene; pos: { top: number; left: number } }) {
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
  const chipRef = useRef<HTMLSpanElement>(null);
  const isHovered = useHover(chipRef as React.RefObject<HTMLElement>);
  const [hoverPos, setHoverPos] = useState({ top: 0, left: 0 });

  const showHover = isHovered && resolvedGene != null;

  if (showHover && chipRef.current) {
    const rect = chipRef.current.getBoundingClientRect();
    const nextPos = { top: rect.bottom + 4, left: rect.left };
    if (nextPos.top !== hoverPos.top || nextPos.left !== hoverPos.left) {
      setHoverPos(nextPos);
    }
  }

  return (
    <>
      <span
        ref={chipRef}
        className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] leading-tight ${statusClasses[status]}`}
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
      {showHover && resolvedGene != null && (
        <GeneHoverCard gene={resolvedGene} pos={hoverPos} />
      )}
    </>
  );
}
