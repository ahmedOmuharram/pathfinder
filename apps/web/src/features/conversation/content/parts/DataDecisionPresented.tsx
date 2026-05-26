"use client";

import { useComposerRuntime } from "@assistant-ui/react";
import type { DecisionPresented } from "@pathfinder/shared";
import type { ReactElement } from "react";
import { GitFork } from "lucide-react";

import { Button } from "@/components/ui/button";

interface DecisionOption {
  readonly id?: string;
  readonly label?: string;
  readonly description?: string;
}

function optionLabel(option: Record<string, unknown>, index: number): string {
  const candidate = (option as DecisionOption).label;
  if (typeof candidate === "string" && candidate !== "") return candidate;
  const id = (option as DecisionOption).id;
  if (typeof id === "string" && id !== "") return id;
  return `Option ${index + 1}`;
}

function optionDescription(option: Record<string, unknown>): string | null {
  const candidate = (option as DecisionOption).description;
  return typeof candidate === "string" && candidate !== "" ? candidate : null;
}

export function DataDecisionPresented({
  data,
}: {
  data: DecisionPresented;
}): ReactElement {
  const composer = useComposerRuntime();

  const handleChoose = (label: string) => {
    composer.setText(label);
    void composer.send();
  };

  return (
    <div
      data-testid="data-decision-presented"
      className="my-2 rounded-lg border border-border bg-card px-3 py-2 text-sm"
    >
      <div className="flex items-center gap-2">
        <GitFork className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        <span className="font-medium">{data.decisionType}</span>
      </div>
      {data.rationale !== null && data.rationale !== undefined && data.rationale !== "" && (
        <p className="mt-1 text-xs text-muted-foreground">{data.rationale}</p>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {data.options.map((option, idx) => {
          const opt = option as Record<string, unknown>;
          const label = optionLabel(opt, idx);
          const description = optionDescription(opt);
          return (
            <Button
              key={label + String(idx)}
              type="button"
              size="sm"
              variant="outline"
              onClick={() => handleChoose(label)}
              className="h-auto whitespace-normal px-3 py-1.5 text-left text-xs"
              title={description ?? undefined}
            >
              {label}
            </Button>
          );
        })}
      </div>
    </div>
  );
}
