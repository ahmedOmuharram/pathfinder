"use client";

/**
 * CompactStrategyView — VEuPathDB-style horizontal strategy strip.
 *
 * Main spine is a single `items-center` row of pills and arrows.
 * For combines, the Venn icon sits inline on the spine, and the
 * secondary input floats above it via absolute positioning.
 */

import { useMemo } from "react";
import { Pencil } from "lucide-react";
import type { StrategyWithMeta } from "@/types/strategy";
import {
  buildSpineLayout,
  type CompactStep,
  type SpineSegment,
} from "@/features/strategy/graph/utils/compactLayout";
import { VennIcon } from "@/features/strategy/graph/components/OpBadge";

// ---------------------------------------------------------------------------
// Style helpers
// ---------------------------------------------------------------------------

const KIND_BORDER: Record<string, string> = {
  search: "border-emerald-400/70",
  combine: "border-sky-400/70",
  transform: "border-violet-400/70",
};

const KIND_COUNT: Record<string, string> = {
  search: "text-emerald-600",
  combine: "text-sky-600",
  transform: "text-violet-600",
};

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

/** Tiny horizontal arrow, vertically centered in the row. */
function Arrow() {
  return (
    <div className="flex shrink-0 items-center px-0.5" aria-hidden>
      <div className="h-px w-3 bg-slate-300" />
      <div className="h-0 w-0 border-y-[2px] border-l-[3px] border-y-transparent border-l-slate-300" />
    </div>
  );
}

/** Step pill — two tight lines: name + count. */
function Pill({ step }: { step: CompactStep }) {
  const border = KIND_BORDER[step.kind] ?? "border-slate-300";
  const countCls = KIND_COUNT[step.kind] ?? "text-slate-500";

  return (
    <div
      className={`shrink-0 rounded border bg-white px-2 py-0.5 text-center leading-none ${border}`}
      style={{ maxWidth: 140 }}
      title={`Step ${step.stepNumber}: ${step.displayName}`}
    >
      <div className="truncate text-[10px] font-semibold text-slate-700">
        {step.displayName}
      </div>
      <div className={`text-[9px] ${countCls}`}>
        {typeof step.resultCount === "number"
          ? `${step.resultCount.toLocaleString()} ${step.recordType ?? ""}`
          : "\u2026"}
      </div>
    </div>
  );
}

/** Venn icon sitting inline on the spine row — no background, scaled up. */
function InlineVenn({ operator }: { operator: string }) {
  return (
    <div className="flex shrink-0 items-center justify-center [&_svg]:mr-0 [&_svg]:h-5 [&_svg]:w-auto">
      <VennIcon operator={operator} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Segment renderers
// ---------------------------------------------------------------------------

/** A plain step (search or transform) — just a pill on the spine. */
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
        {/* Secondary input — absolute, floating above the Venn dot */}
        <div className="absolute bottom-full left-1/2 mb-0.5 flex -translate-x-1/2 flex-col items-center">
          <Pill step={secondaryInput} />
          <div className="h-1.5 w-px bg-slate-300" />
        </div>
        <InlineVenn operator={step.operator!} />
      </div>
      <Arrow />
      <Pill step={step} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface CompactStrategyViewProps {
  strategy: StrategyWithMeta | null;
  onEditGraph?: () => void;
}

export function CompactStrategyView({
  strategy,
  onEditGraph,
}: CompactStrategyViewProps) {
  const spine = useMemo(() => {
    if (!strategy?.steps?.length || !strategy.rootStepId) return [];
    return buildSpineLayout(strategy.steps, strategy.rootStepId);
  }, [strategy]);

  if (!strategy || spine.length === 0) return null;

  return (
    <div className="border-t border-slate-200 bg-slate-50/80">
      <div className="flex items-center gap-0">
        {/* Scrollable spine */}
        <div className="flex min-w-0 flex-1 items-center overflow-x-auto px-4 pb-3 pt-10">
          {spine.map((seg, i) => (
            <div key={seg.step.id} className="flex items-center">
              {i > 0 && <Arrow />}
              {seg.secondaryInput && seg.step.operator ? (
                <CombineSegment step={seg.step} secondaryInput={seg.secondaryInput} />
              ) : (
                <PlainSegment step={seg.step} />
              )}
            </div>
          ))}
        </div>

        {/* Edit button — pinned outside the scroll area */}
        {onEditGraph && (
          <button
            type="button"
            onClick={onEditGraph}
            className="mr-3 inline-flex shrink-0 items-center gap-1 self-center rounded border border-dashed border-slate-300 bg-white px-2 py-1 text-[10px] font-medium text-slate-500 transition hover:border-slate-400 hover:text-slate-700"
          >
            <Pencil className="h-2.5 w-2.5" aria-hidden />
            Edit
          </button>
        )}
      </div>
    </div>
  );
}
