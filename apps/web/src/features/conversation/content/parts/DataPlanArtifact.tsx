import type { PlanArtifact, PlannedStep } from "@pathfinder/shared";
import { ClipboardList } from "lucide-react";

export function DataPlanArtifact({ data }: { data: PlanArtifact }) {
  const steps = data.steps;
  return (
    <div
      data-testid="data-plan-artifact"
      className="my-2 rounded-md border border-border bg-card px-3 py-2 text-xs"
    >
      <div className="flex items-center gap-2">
        <ClipboardList className="size-3.5 text-muted-foreground" aria-hidden />
        <span className="text-sm font-medium">Proposed Plan</span>
        <span className="ml-auto text-muted-foreground">
          {steps.length} {steps.length === 1 ? "step" : "steps"}
        </span>
      </div>
      {data.rationale !== "" && (
        <p className="mt-1 text-muted-foreground">{data.rationale}</p>
      )}
      <ol className="mt-2 space-y-2">
        {steps.map((step, idx) => (
          <StepRow key={`${step.searchName}-${idx}`} step={step} index={idx} />
        ))}
      </ol>
    </div>
  );
}

function StepRow({ step, index }: { step: PlannedStep; index: number }) {
  const params = step.parameters ?? {};
  const paramEntries = Object.entries(params).filter(
    ([, value]) => value !== null && value !== undefined && value !== "",
  );
  return (
    <li className="rounded-md border border-border/60 bg-muted/20 p-2">
      <div className="flex items-baseline gap-2">
        <span className="text-[11px] font-semibold text-muted-foreground tabular-nums">
          {index + 1}.
        </span>
        <span className="break-all font-mono text-[11px] text-foreground">
          {step.searchName}
        </span>
      </div>
      {step.rationale != null && step.rationale !== "" && (
        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
          {step.rationale}
        </p>
      )}
      {paramEntries.length > 0 && (
        <dl className="mt-1.5 space-y-0.5 border-t border-border/50 pt-1.5">
          {paramEntries.map(([key, value]) => (
            <div key={key} className="flex gap-2 text-[10px]">
              <dt className="w-28 shrink-0 break-all font-mono text-muted-foreground">
                {key}
              </dt>
              <dd className="min-w-0 flex-1 break-words font-mono text-foreground">
                {formatParamValue(value)}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </li>
  );
}

function formatParamValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}
