"use client";

import type { Step, Strategy } from "@pathfinder/shared";
import { Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  buildSpineLayout,
  findOrphanSteps,
  type CompactStep,
} from "@/features/strategy/graph/utils/compactLayout";
import { VennIcon } from "@/features/strategy/graph/components/OpBadge";
import { inferStepKind } from "@/lib/strategyGraph";
import { usePushStrategyMutation } from "@/features/strategy/mutations/usePushStrategyMutation";
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
  /** Step id currently focused by the URL / editor sheet. */
  selectedStepId?: string | null;
}

export function CompactStrategyView({
  strategy,
  onStepClick,
  selectedStepId = null,
}: CompactStrategyViewProps) {
  if (strategy == null) return null;

  const spine =
    strategy.steps.length === 0 ||
    strategy.rootStepId == null ||
    strategy.rootStepId === ""
      ? []
      : buildSpineLayout(strategy.steps, strategy.rootStepId);

  const orphans = findOrphanSteps(strategy.steps, strategy.rootStepId ?? null);

  if (spine.length === 0 && orphans.length === 0) {
    return (
      <div className="px-3 py-3 text-xs text-muted-foreground">
        Building strategy ({strategy.steps.length} steps)…
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 px-3 py-3">
      {spine.length > 0 && (
        <ol
          data-testid="compact-strategy-view"
          className="flex flex-col gap-1"
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
                  selectedStepId={selectedStepId}
                  {...(onStepClick !== undefined && { onStepClick })}
                />
              );
            }
            return (
              <StepRow
                key={seg.step.id}
                step={seg.step}
                selectedStepId={selectedStepId}
                {...(onStepClick !== undefined && { onStepClick })}
              />
            );
          })}
        </ol>
      )}
      {orphans.length > 0 && (
        <DisconnectedSection
          strategy={strategy}
          orphans={orphans}
          selectedStepId={selectedStepId}
          {...(onStepClick !== undefined && { onStepClick })}
        />
      )}
    </div>
  );
}

interface DisconnectedSectionProps {
  strategy: Strategy;
  orphans: Step[];
  onStepClick?: (stepId: string) => void;
  selectedStepId?: string | null;
}

function DisconnectedSection({
  strategy,
  orphans,
  onStepClick,
  selectedStepId = null,
}: DisconnectedSectionProps) {
  const push = usePushStrategyMutation();
  const orphanIds = new Set(orphans.map((s) => s.id));
  const handleClear = () => {
    push.mutate({
      optimistic: {
        ...strategy,
        steps: strategy.steps.filter((s) => !orphanIds.has(s.id)),
      },
    });
  };
  return (
    <section
      data-testid="compact-strategy-orphans"
      className="rounded-md border border-dashed border-amber-500/50 bg-amber-500/5 p-2"
    >
      <header className="mb-1 flex items-center justify-between gap-2 px-1 text-[10px] uppercase tracking-wide text-amber-700 dark:text-amber-400">
        <span>{orphans.length} disconnected</span>
        <Button
          type="button"
          size="xs"
          variant="ghost"
          onClick={handleClear}
          disabled={push.isPending}
          className="h-5 gap-1 px-1.5 text-[10px] text-amber-700 hover:text-amber-900 dark:text-amber-400 dark:hover:text-amber-200"
        >
          <Trash2 className="size-3" aria-hidden /> Remove all
        </Button>
      </header>
      <p className="px-1 pb-1 text-[10px] text-muted-foreground">
        These steps aren&apos;t connected and block save. Remove or wire
        them up in the full editor.
      </p>
      <ol className="flex flex-col gap-0.5">
        {orphans.map((step) => (
          <OrphanRow
            key={step.id}
            step={step}
            isSelected={step.id === selectedStepId}
            {...(onStepClick !== undefined && { onStepClick })}
          />
        ))}
      </ol>
    </section>
  );
}

interface OrphanRowProps {
  step: Step;
  onStepClick?: (stepId: string) => void;
  isSelected?: boolean;
}

function OrphanRow({ step, onStepClick, isSelected = false }: OrphanRowProps) {
  const kind = inferStepKind(step);
  const dot = KIND_DOT[kind] ?? "bg-muted";
  const displayName = step.displayName ?? step.searchName ?? step.id;
  return (
    <li>
      <button
        type="button"
        onClick={() => onStepClick?.(step.id)}
        data-testid={`compact-orphan-row-${step.id}`}
        aria-current={isSelected ? "true" : undefined}
        className={cn(
          "flex w-full items-center gap-2 rounded px-2 py-1 text-left text-xs text-muted-foreground opacity-70 transition-opacity hover:bg-accent hover:opacity-100",
          isSelected && "bg-accent text-foreground opacity-100 ring-1 ring-primary/50",
        )}
      >
        <span
          aria-hidden
          className={cn("inline-block size-2 shrink-0 rounded-full", dot)}
        />
        <span className="flex-1 truncate">{displayName}</span>
      </button>
    </li>
  );
}

interface StepRowProps {
  step: CompactStep;
  onStepClick?: (stepId: string) => void;
  indented?: boolean;
  selectedStepId?: string | null;
}

function StepRow({
  step, onStepClick, indented = false, selectedStepId = null,
}: StepRowProps) {
  return (
    <li>
      <StepRowButton
        step={step}
        selectedStepId={selectedStepId}
        {...(onStepClick !== undefined && { onStepClick })}
        indented={indented}
      />
    </li>
  );
}

function StepRowButton({
  step, onStepClick, indented = false, selectedStepId = null,
}: StepRowProps) {
  const dot = KIND_DOT[step.kind] ?? "bg-muted";
  const snapshot = useStepSnapshot(step);
  const liveCount = snapshot.estimatedSize;
  const isSelected = step.id === selectedStepId;

  return (
    <button
      type="button"
      onClick={() => onStepClick?.(step.id)}
      data-testid={`compact-step-row-${step.id}`}
      aria-current={isSelected ? "true" : undefined}
      className={cn(
        isSelected && "bg-accent ring-1 ring-primary/50",
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
  selectedStepId?: string | null;
}

function CombineRow({
  step, secondaryInput, onStepClick, selectedStepId = null,
}: CombineRowProps) {
  const operator = step.operator ?? "";
  const operatorLabel = combineOperatorLabel(operator);

  return (
    <li className="space-y-0.5">
      <StepRowButton
        step={secondaryInput}
        selectedStepId={selectedStepId}
        {...(onStepClick !== undefined && { onStepClick })}
        indented
      />
      <div className="ml-4 flex items-center gap-2 px-2 py-1 text-[10px] uppercase tracking-wide text-muted-foreground">
        <VennIcon operator={operator} />
        <span>Combine ({operatorLabel})</span>
      </div>
      <StepRowButton
        step={step}
        selectedStepId={selectedStepId}
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
