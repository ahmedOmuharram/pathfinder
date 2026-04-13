"use client";

/**
 * Popover list of @-mention suggestions shown below the composer textarea.
 *
 * Renders candidates from `useMentionSuggestions`. Keyboard navigation is
 * driven by the parent `ChatInput`, which forwards arrow/enter keys via the
 * `activeIndex` prop. Clicking an item selects it directly.
 */

import { FileText, Layers, Network } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { MentionCandidate, MentionKind } from "./useMentionSuggestions";

const KIND_META: Record<MentionKind, { Icon: LucideIcon; label: string }> = {
  strategy: { Icon: Network, label: "Strategy" },
  step: { Icon: Layers, label: "Step" },
  geneset: { Icon: FileText, label: "Gene set" },
};

export function MentionDropdown({
  candidates,
  activeIndex,
  onSelect,
}: {
  candidates: readonly MentionCandidate[];
  activeIndex: number;
  onSelect: (candidate: MentionCandidate) => void;
}) {
  if (candidates.length === 0) return null;
  return (
    <div
      role="listbox"
      aria-label="Mentions"
      data-testid="mention-dropdown"
      className="absolute bottom-full left-0 z-30 mb-1 w-80 max-w-full overflow-hidden rounded-md border border-border bg-card shadow-lg"
    >
      <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        References
      </div>
      {candidates.map((candidate, idx) => {
        const { Icon, label: kindLabel } = KIND_META[candidate.kind];
        const isActive = idx === activeIndex;
        return (
          <button
            key={`${candidate.kind}-${candidate.id}`}
            type="button"
            role="option"
            aria-selected={isActive}
            data-testid={`mention-option-${candidate.kind}-${candidate.id}`}
            onMouseDown={(event) => {
              event.preventDefault();
              onSelect(candidate);
            }}
            className={`flex w-full items-start gap-2 px-2 py-1.5 text-left text-xs transition-colors ${
              isActive
                ? "bg-accent text-accent-foreground"
                : "hover:bg-accent/50"
            }`}
          >
            <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium text-foreground">
                {candidate.label}
              </div>
              <div className="truncate text-[10px] text-muted-foreground">
                {kindLabel}
                {candidate.sublabel !== undefined && ` · ${candidate.sublabel}`}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
