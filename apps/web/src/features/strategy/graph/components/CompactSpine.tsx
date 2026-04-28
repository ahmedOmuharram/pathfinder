"use client";

import type { Step } from "@pathfinder/shared";
import { Bookmark } from "lucide-react";

import { CompactRowKebab } from "@/features/strategy/graph/components/CompactRowKebab";
import { VennIcon } from "@/features/strategy/graph/components/OpBadge";
import {
  buildSpineLayout,
  type CompactStep,
} from "@/features/strategy/graph/utils/compactLayout";
import { useStepSnapshot } from "@/state/strategy/useStepSnapshot";
import { cn } from "@/lib/utils/cn";

const KIND_DOT: Record<string, string> = {
  search: "bg-[hsl(var(--kind-leaf))]",
  combine: "bg-[hsl(var(--kind-combine))]",
  transform: "bg-[hsl(var(--kind-transform))]",
};

interface RowActions {
  onStepClick?: (stepId: string) => void;
  selectedStepId?: string | null;
  onSaveStep?: (stepId: string) => void;
  onInsertSavedAt?: (stepId: string) => void;
}

interface StepRowProps extends RowActions {
  step: CompactStep;
  indented?: boolean;
}

export function CompactStepRow({
  step,
  onStepClick,
  indented = false,
  selectedStepId = null,
  onSaveStep,
  onInsertSavedAt,
}: StepRowProps) {
  return (
    <li className="flex items-center gap-1">
      <StepRowButton
        step={step}
        selectedStepId={selectedStepId}
        {...(onStepClick !== undefined && { onStepClick })}
        indented={indented}
      />
      {(onSaveStep != null || onInsertSavedAt != null) && (
        <CompactRowKebab
          stepId={step.id}
          {...(onSaveStep !== undefined && { onSaveStep })}
          {...(onInsertSavedAt !== undefined && { onInsertSavedAt })}
        />
      )}
    </li>
  );
}

function StepRowButton({
  step,
  onStepClick,
  indented = false,
  selectedStepId = null,
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

interface SpineSegmentRowProps extends RowActions {
  segment: { step: CompactStep; secondaryInput?: CompactStep };
  allSteps: Step[];
  /** 0 = top-level strategy, 1+ = inside an expanded saved-strategy. */
  level: number;
}

export function CompactSpineSegmentRow({
  segment,
  allSteps,
  onStepClick,
  selectedStepId = null,
  level,
  onSaveStep,
  onInsertSavedAt,
}: SpineSegmentRowProps) {
  const isCombine =
    segment.secondaryInput != null &&
    segment.step.operator != null &&
    segment.step.operator !== "";
  if (!isCombine || segment.secondaryInput == null) {
    return (
      <CompactStepRow
        step={segment.step}
        selectedStepId={selectedStepId}
        {...(onStepClick !== undefined && { onStepClick })}
        {...(onSaveStep !== undefined && { onSaveStep })}
        {...(onInsertSavedAt !== undefined && { onInsertSavedAt })}
      />
    );
  }
  return (
    <CombineRow
      step={segment.step}
      secondaryInput={segment.secondaryInput}
      allSteps={allSteps}
      selectedStepId={selectedStepId}
      level={level}
      {...(onStepClick !== undefined && { onStepClick })}
      {...(onSaveStep !== undefined && { onSaveStep })}
      {...(onInsertSavedAt !== undefined && { onInsertSavedAt })}
    />
  );
}

interface CombineRowProps extends RowActions {
  step: CompactStep;
  secondaryInput: CompactStep;
  allSteps: Step[];
  level: number;
}

function CombineRow({
  step,
  secondaryInput,
  allSteps,
  onStepClick,
  selectedStepId = null,
  level,
  onSaveStep,
  onInsertSavedAt,
}: CombineRowProps) {
  const operator = step.operator ?? "";
  const isExpandedSaved =
    step.expandedStrategyId != null && step.expandedName != null;
  return (
    <li className="space-y-0.5">
      {isExpandedSaved ? (
        <SavedSubstrategyContainer
          name={step.expandedName ?? ""}
          rootStepId={secondaryInput.id}
          allSteps={allSteps}
          selectedStepId={selectedStepId}
          level={level + 1}
          {...(onStepClick !== undefined && { onStepClick })}
          {...(onSaveStep !== undefined && { onSaveStep })}
          {...(onInsertSavedAt !== undefined && { onInsertSavedAt })}
        />
      ) : (
        <div className="flex items-center gap-1">
          <StepRowButton
            step={secondaryInput}
            selectedStepId={selectedStepId}
            {...(onStepClick !== undefined && { onStepClick })}
            indented
          />
          {(onSaveStep != null || onInsertSavedAt != null) && (
            <CompactRowKebab
              stepId={secondaryInput.id}
              {...(onSaveStep !== undefined && { onSaveStep })}
              {...(onInsertSavedAt !== undefined && { onInsertSavedAt })}
            />
          )}
        </div>
      )}
      <div className="ml-4 flex items-center gap-2 px-2 py-1 text-[10px] uppercase tracking-wide text-muted-foreground">
        <VennIcon operator={operator} />
        <span>Combine ({combineOperatorLabel(operator)})</span>
      </div>
      <div className="flex items-center gap-1">
        <StepRowButton
          step={step}
          selectedStepId={selectedStepId}
          {...(onStepClick !== undefined && { onStepClick })}
        />
        {(onSaveStep != null || onInsertSavedAt != null) && (
          <CompactRowKebab
            stepId={step.id}
            {...(onSaveStep !== undefined && { onSaveStep })}
            {...(onInsertSavedAt !== undefined && { onInsertSavedAt })}
          />
        )}
      </div>
    </li>
  );
}

interface SavedSubstrategyContainerProps extends RowActions {
  name: string;
  rootStepId: string;
  allSteps: Step[];
  level: number;
}

function SavedSubstrategyContainer({
  name,
  rootStepId,
  allSteps,
  onStepClick,
  selectedStepId = null,
  level,
  onSaveStep,
  onInsertSavedAt,
}: SavedSubstrategyContainerProps) {
  const innerSpine = buildSpineLayout(allSteps, rootStepId);
  const tone = level >= 3 ? 3 : level;
  const toneBg = ["", "bg-primary/5", "bg-primary/10", "bg-primary/15"][tone];
  return (
    <section
      data-testid="saved-substrategy-container"
      className={cn(
        "ml-4 rounded-md border border-dashed border-primary/40 p-1.5",
        toneBg,
      )}
    >
      <header className="mb-1 flex items-center gap-2 px-1 text-[10px] uppercase tracking-wide text-primary/80">
        <Bookmark className="size-3" aria-hidden />
        <span className="truncate font-semibold">{name}</span>
        <span className="ml-auto text-muted-foreground">level {level}</span>
      </header>
      <ol className="flex flex-col gap-0.5">
        {innerSpine.map((seg) => (
          <CompactSpineSegmentRow
            key={seg.step.id}
            segment={seg}
            allSteps={allSteps}
            selectedStepId={selectedStepId}
            level={level}
            {...(onStepClick !== undefined && { onStepClick })}
            {...(onSaveStep !== undefined && { onSaveStep })}
            {...(onInsertSavedAt !== undefined && { onInsertSavedAt })}
          />
        ))}
      </ol>
    </section>
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
