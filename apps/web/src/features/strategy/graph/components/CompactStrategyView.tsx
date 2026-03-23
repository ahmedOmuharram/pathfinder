"use client";

/**
 * CompactStrategyView -- VEuPathDB-style horizontal strategy strip.
 *
 * Main spine is a single `items-center` row of pills and arrows.
 * For combines, the Venn icon sits inline on the spine, and the
 * secondary input floats above it via absolute positioning.
 */

import { useMemo } from "react";
import { Layers, Loader2, Pencil } from "lucide-react";
import type { Strategy } from "@pathfinder/shared";
import {
  buildSpineLayout,
  type CompactStep,
} from "@/features/strategy/graph/utils/compactLayout";
import { VennIcon } from "@/features/strategy/graph/components/OpBadge";

// Style helpers

const KIND_BORDER: Record<string, string> = {
  search: "border-[hsl(var(--kind-leaf)/0.7)]",
  combine: "border-[hsl(var(--kind-combine)/0.7)]",
  transform: "border-[hsl(var(--kind-transform)/0.7)]",
};

const KIND_COUNT: Record<string, string> = {
  search: "text-[hsl(var(--kind-leaf))]",
  combine: "text-[hsl(var(--kind-combine))]",
  transform: "text-[hsl(var(--kind-transform))]",
};

// Primitives

/** Tiny horizontal arrow, vertically centered in the row. */
function Arrow() {
  return (
    <div className="flex shrink-0 items-center px-0.5" aria-hidden>
      <div className="h-px w-3 bg-border" />
      <div className="h-0 w-0 border-y-[2px] border-l-[3px] border-y-transparent border-l-border" />
    </div>
  );
}

/** Step pill -- two tight lines: name + count. */
function Pill({ step }: { step: CompactStep }) {
  const border = KIND_BORDER[step.kind] ?? "border-border";
  const countCls = KIND_COUNT[step.kind] ?? "text-muted-foreground";

  return (
    <div
      className={`shrink-0 rounded border bg-card px-2 py-0.5 text-center leading-none ${border}`}
      style={{ maxWidth: 140 }}
      title={`Step ${step.stepNumber}: ${step.displayName}`}
    >
      <div className="truncate text-xs font-semibold text-foreground">
        {step.displayName}
      </div>
      <div className={`text-xs ${countCls}`}>
        {typeof step.estimatedSize === "number"
          ? `${step.estimatedSize.toLocaleString()} ${step.recordType ?? ""}`
          : "\u2026"}
      </div>
    </div>
  );
}

/** Venn icon sitting inline on the spine row -- no background, scaled up. */
function InlineVenn({ operator }: { operator: string }) {
  return (
    <div className="flex shrink-0 items-center justify-center [&_svg]:mr-0 [&_svg]:h-5 [&_svg]:w-auto">
      <VennIcon operator={operator} />
    </div>
  );
}

// Segment renderers

/** A plain step (search or transform) -- just a pill on the spine. */
function PlainSegment({ step }: { step: CompactStep }) {
  return <Pill step={step} />;
}

/**
 * Combine segment: secondary input floats above the Venn icon (absolute),
 * while the Venn icon itself sits inline on the spine row, centered with
 * the arrows and other pills.
 */
function CombineSegment({
  step,
  secondaryInput,
}: {
  step: CompactStep;
  secondaryInput: CompactStep;
}) {
  return (
    <div className="flex items-center">
      {/* Venn icon with secondary floating above */}
      <div className="relative flex items-center justify-center">
        {/* Secondary input -- absolute, floating above the Venn dot */}
        <div className="absolute bottom-full left-1/2 mb-0.5 flex -translate-x-1/2 flex-col items-center">
          <Pill step={secondaryInput} />
          <div className="h-1.5 w-px bg-border" />
        </div>
        <InlineVenn operator={step.operator!} />
      </div>
      <Arrow />
      <Pill step={step} />
    </div>
  );
}

// Main component

interface CompactStrategyViewProps {
  strategy: Strategy | null;
  onEditGraph?: () => void;
  /** Callback to export strategy results as a gene set in the workbench. */
  onExportAsGeneSet?: (strategy: Strategy) => void;
  /** Whether the export operation is in progress. */
  exportingGeneSet?: boolean;
}

export function CompactStrategyView({
  strategy,
  onEditGraph,
  onExportAsGeneSet,
  exportingGeneSet = false,
}: CompactStrategyViewProps) {
  const spine = useMemo(() => {
    if (
      strategy == null ||
      strategy.steps.length === 0 ||
      strategy.rootStepId == null ||
      strategy.rootStepId === ""
    )
      return [];
    return buildSpineLayout(strategy.steps, strategy.rootStepId);
  }, [strategy]);

  const canOpenInWorkbench =
    strategy?.wdkStrategyId != null && onExportAsGeneSet != null;

  if (strategy == null || spine.length === 0) return null;

  return (
    <div className="border-t border-border bg-muted">
      <div className="flex items-center gap-0">
        {/* Scrollable spine */}
        <div className="flex min-w-0 flex-1 items-center overflow-x-auto px-4 pb-3 pt-10">
          {spine.map((seg, i) => (
            <div key={seg.step.id} className="flex items-center">
              {i > 0 && <Arrow />}
              {seg.secondaryInput != null &&
              seg.step.operator != null &&
              seg.step.operator !== "" ? (
                <CombineSegment step={seg.step} secondaryInput={seg.secondaryInput} />
              ) : (
                <PlainSegment step={seg.step} />
              )}
            </div>
          ))}
        </div>

        {/* Action buttons -- pinned outside the scroll area */}
        <div className="mr-3 flex shrink-0 items-center gap-1.5 self-center">
          {canOpenInWorkbench && (
            <button
              type="button"
              onClick={() => onExportAsGeneSet(strategy)}
              disabled={exportingGeneSet}
              className="inline-flex shrink-0 items-center gap-1 rounded border border-dashed border-border bg-card px-2 py-1 text-xs font-medium text-muted-foreground transition-colors duration-150 hover:border-input hover:text-foreground disabled:opacity-50"
            >
              {exportingGeneSet ? (
                <Loader2 className="h-2.5 w-2.5 animate-spin" aria-hidden />
              ) : (
                <Layers className="h-2.5 w-2.5" aria-hidden />
              )}
              Workbench
            </button>
          )}

          {onEditGraph && (
            <button
              type="button"
              onClick={onEditGraph}
              className="inline-flex shrink-0 items-center gap-1 rounded border border-dashed border-border bg-card px-2 py-1 text-xs font-medium text-muted-foreground transition-colors duration-150 hover:border-input hover:text-foreground"
            >
              <Pencil className="h-2.5 w-2.5" aria-hidden />
              Edit
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
