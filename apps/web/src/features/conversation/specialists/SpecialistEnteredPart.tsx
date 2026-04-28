import type { DataSpecialistEnteredPayload } from "@pathfinder/shared";
import { ChevronRight, Microscope, Search } from "lucide-react";

import { cn } from "@/lib/utils/cn";

const KIND_LABELS: Record<DataSpecialistEnteredPayload["kind"], string> = {
  validate: "Validate",
  research: "Research",
};

const KIND_TINT: Record<DataSpecialistEnteredPayload["kind"], string> = {
  validate: "border-primary/30 bg-primary/10 text-foreground",
  research:
    "border-secondary-foreground/15 bg-secondary text-secondary-foreground",
};

export function SpecialistEnteredPart({
  data,
}: {
  data: DataSpecialistEnteredPayload;
}) {
  const Icon = data.kind === "validate" ? Microscope : Search;
  return (
    <div
      data-testid="data-specialist-entered"
      data-kind={data.kind}
      data-specialist-bracket="open"
      className={cn(
        "my-2 flex min-w-0 items-center gap-2 rounded-md border px-3 py-1.5 text-xs",
        KIND_TINT[data.kind],
      )}
    >
      <Icon className="size-3.5 shrink-0" aria-hidden />
      <span className="shrink-0 font-medium">
        {KIND_LABELS[data.kind]} session started
      </span>
      <span aria-hidden className="shrink-0 opacity-50">·</span>
      <span className="shrink-0 font-mono opacity-80">{data.modelId}</span>
      {data.contextSummary !== "" ? (
        <>
          <ChevronRight className="size-3 shrink-0 opacity-60" aria-hidden />
          <span className="min-w-0 flex-1 truncate opacity-80">
            {data.contextSummary}
          </span>
        </>
      ) : null}
    </div>
  );
}
