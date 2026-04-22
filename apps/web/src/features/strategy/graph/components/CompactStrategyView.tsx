"use client";

/**
 * CompactStrategyView — read-only vertical step list rendered in the right
 * rail's StrategyPanel.
 *
 * Walks the spine via `buildSpineLayout`. Search and transform steps render
 * as a single row (dot + name + count). Combine steps render as an indented
 * sub-tree (secondary input + venn glyph + result row).
 */

import type { Strategy } from "@pathfinder/shared";
import {
  buildSpineLayout,
  type CompactStep,
} from "@/features/strategy/graph/utils/compactLayout";
import { VennIcon } from "@/features/strategy/graph/components/OpBadge";
import { useStepSnapshot } from "@/state/strategy/useStepSnapshot";
import { cn } from "@/lib/utils/cn";

const KIND_DOT: Record<string, string> = {
  search: "bg-[hsl(var(--kind-leaf))]",
  combine: "bg-[hsl(var(--kind-combine))]",
  transform: "bg-[hsl(var(--kind-transform))]",
};

interface CompactStrategyViewProps {
  strategy: Strategy | null;
  /** Click handler for any step row. Receives the step id. */
  onStepClick?: (stepId: string) => void;
}

export function CompactStrategyView({
  strategy,
  onStepClick,
}: CompactStrategyViewProps) {
  if (strategy == null) return null;

  const spine =
    strategy.steps.length === 0 ||
    strategy.rootStepId == null ||
    strategy.rootStepId === ""
      ? []
      : buildSpineLayout(strategy.steps, strategy.rootStepId);

  if (spine.length === 0) {
    return (
      <div className="px-3 py-3 text-xs text-muted-foreground">
        Building strategy ({strategy.steps.length} steps)…
      </div>
    );
  }

  return (
    <ol
      data-testid="compact-strategy-view"
      className="flex flex-col gap-1 px-3 py-3"
    >
      {spine.map((seg) => {
        const isCombine =
          seg.secondaryInput != null &&
          seg.step.operator != null &&
          seg.step.operator !== "";
        if (isCombine && seg.secondaryInput) {
          return (
            <CombineRow
              key={seg.step.id}
              step={seg.step}
              secondaryInput={seg.secondaryInput}
              {...(onStepClick !== undefined && { onStepClick })}
            />
          );
        }
        return (
          <StepRow
            key={seg.step.id}
            step={seg.step}
            {...(onStepClick !== undefined && { onStepClick })}
          />
        );
      })}
    </ol>
  );
}

interface StepRowProps {
  step: CompactStep;
  onStepClick?: (stepId: string) => void;
  indented?: boolean;
}

function StepRow({ step, onStepClick, indented = false }: StepRowProps) {
  return (
    <li>
      <StepRowButton
        step={step}
        {...(onStepClick !== undefined && { onStepClick })}
        indented={indented}
      />
    </li>
  );
}

function StepRowButton({ step, onStepClick, indented = false }: StepRowProps) {
  const dot = KIND_DOT[step.kind] ?? "bg-muted";
  const snapshot = useStepSnapshot(step.id);
  const liveCount = snapshot.estimatedSize;

  return (
    <button
      type="button"
      onClick={() => onStepClick?.(step.id)}
      data-testid={`compact-step-row-${step.id}`}
      className={cn(
        "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-accent",
        indented && "ml-4",
      )}
    >
      <span
        aria-hidden
        className={cn("inline-block size-2 shrink-0 rounded-full", dot)}
      />
      <span className="flex-1 truncate text-xs font-medium text-foreground">
        {step.displayName}
      </span>
      <span className="text-[10px] tabular-nums text-muted-foreground">
        {typeof liveCount === "number" ? liveCount.toLocaleString() : "…"}
      </span>
    </button>
  );
}

interface CombineRowProps {
  step: CompactStep;
  secondaryInput: CompactStep;
  onStepClick?: (stepId: string) => void;
}

function CombineRow({ step, secondaryInput, onStepClick }: CombineRowProps) {
  const operator = step.operator ?? "";
  const operatorLabel = combineOperatorLabel(operator);

  return (
    <li className="space-y-0.5">
      <StepRowButton
        step={secondaryInput}
        {...(onStepClick !== undefined && { onStepClick })}
        indented
      />
      <div className="ml-4 flex items-center gap-2 px-2 py-1 text-[10px] uppercase tracking-wide text-muted-foreground">
        <VennIcon operator={operator} />
        <span>Combine ({operatorLabel})</span>
      </div>
      <StepRowButton
        step={step}
        {...(onStepClick !== undefined && { onStepClick })}
      />
    </li>
  );
}

function combineOperatorLabel(operator: string): string {
  switch (operator) {
    case "INTERSECT":
      return "A ∩ B";
    case "UNION":
      return "A ∪ B";
    case "MINUS":
      return "A − B";
    case "RMINUS":
      return "B − A";
    case "LONLY":
      return "A only";
    case "RONLY":
      return "B only";
    case "COLOCATE":
      return "near";
    default:
      return operator;
  }
}
