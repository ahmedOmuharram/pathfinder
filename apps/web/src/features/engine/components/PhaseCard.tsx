import type { ModelCatalogEntry, PipelinePhase, PipelinePhaseConfig, ReasoningEffort } from "@pathfinder/shared";
import { cn } from "@/lib/utils/cn";

interface PhaseCardProps {
  phase: PipelinePhase;
  config: PipelinePhaseConfig;
  models: ModelCatalogEntry[];
  isSelected: boolean;
  onSelect: () => void;
  onEffortChange: (effort: ReasoningEffort) => void;
}

const PHASE_LABELS: Record<PipelinePhase, string> = {
  discovery: "Discovery",
  planning: "Planning",
  execution: "Execution",
  verification: "Verification",
};

const EFFORT_OPTIONS: ReasoningEffort[] = ["none", "low", "medium", "high"];

export function PhaseCard({
  phase,
  config,
  models,
  isSelected,
  onSelect,
  onEffortChange,
}: PhaseCardProps) {
  const model = models.find((m) => m.id === config.modelId);
  const displayName = model?.name ?? config.modelId;

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded-lg border p-3 text-left transition-colors",
        "cursor-pointer hover:border-primary/50",
        isSelected && "border-primary bg-primary/5 ring-1 ring-primary/20",
      )}
    >
      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
        {PHASE_LABELS[phase]}
      </div>
      <div className="mt-1 text-sm font-semibold">{displayName}</div>
      <div className="mt-1 flex items-center gap-1.5">
        <select
          value={config.reasoningEffort}
          onChange={(e) => onEffortChange(e.target.value as ReasoningEffort)}
          onClick={(e) => e.stopPropagation()}
          className="rounded border bg-background px-1.5 py-0.5 text-xs"
        >
          {EFFORT_OPTIONS.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </div>
    </button>
  );
}
