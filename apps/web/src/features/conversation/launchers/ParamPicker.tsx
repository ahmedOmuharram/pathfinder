"use client";

import { useStore } from "@tanstack/react-form";
import { Check, X as XIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useParamSpecs } from "@/lib/hooks/useParamSpecs";
import { cn } from "@/lib/utils/cn";

import type { LauncherForm } from "./optimizeFormTypes";

const SWEEPABLE_TYPES: ReadonlySet<string> = new Set([
  "string",
  "number",
  "numberRange",
  "date",
  "dateRange",
  "timestamp",
  "filter",
  "enum",
  "treeBoxEnum",
  "checkBoxEnum",
  "typeAheadEnum",
  "selectEnum",
]);

interface SweepableSpec {
  type: string;
  isMulti?: boolean;
  isVisible?: boolean | null;
}

function isSweepable(spec: SweepableSpec): boolean {
  if (spec.isVisible === false) return false;
  if (spec.isMulti === true) return false;
  return SWEEPABLE_TYPES.has(spec.type);
}

function FieldShell({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}

export function ParamPicker({
  form,
  siteId,
  recordType,
  stepSearchName,
}: {
  form: LauncherForm;
  siteId: string;
  recordType: string;
  stepSearchName: string;
}) {
  const value = useStore(form.store, (s) => s.values.paramKeys);
  const { paramSpecs, isLoading } = useParamSpecs(
    siteId,
    recordType,
    stepSearchName,
  );
  const sweepable = paramSpecs.filter(isSweepable);
  const known = new Set(sweepable.map((p) => p.name));

  return (
    <FieldShell
      label={
        <>
          Parameters to tune
          {stepSearchName !== "" ? (
            <span className="ml-1 font-mono normal-case text-muted-foreground/70">
              ({stepSearchName})
            </span>
          ) : null}
        </>
      }
    >
      {value.length > 0 ? (
        <div className="mb-1 flex flex-wrap gap-1" data-testid="optimize-paramkeys-chips">
          {value.map((key) => (
            <Badge
              key={key}
              variant="secondary"
              className="gap-1 font-mono text-[10px]"
            >
              {key}
              <button
                type="button"
                onClick={() =>
                  form.setParamKeys(value.filter((k) => k !== key))
                }
                className="rounded hover:bg-black/10 dark:hover:bg-white/10"
                aria-label={`Remove ${key}`}
              >
                <XIcon className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      ) : null}

      <Popover>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={stepSearchName === ""}
            data-testid="optimize-paramkeys-trigger"
            className="w-full justify-between text-left text-xs font-normal"
          >
            <span className="truncate">{triggerLabel(value, sweepable.length, isLoading, stepSearchName)}</span>
            <span className="ml-2 text-muted-foreground">⌄</span>
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="start"
          className="w-72 p-1"
          data-testid="optimize-paramkeys-popover"
        >
          <ul className="max-h-64 overflow-auto py-1">
            {sweepable.map((spec) => {
              const selected = value.includes(spec.name);
              return (
                <li key={spec.name}>
                  <button
                    type="button"
                    onClick={() => {
                      if (selected) {
                        form.setParamKeys(value.filter((k) => k !== spec.name));
                      } else {
                        form.setParamKeys([...value, spec.name]);
                      }
                    }}
                    className={cn(
                      "flex w-full items-center justify-between rounded-sm px-2 py-1 text-left text-xs",
                      "hover:bg-muted",
                    )}
                    data-testid={`optimize-paramkeys-option-${spec.name}`}
                  >
                    <span>
                      <span className="font-mono">{spec.name}</span>
                      {spec.displayName !== "" && spec.displayName !== spec.name ? (
                        <span className="ml-1 text-muted-foreground">
                          {spec.displayName}
                        </span>
                      ) : null}
                    </span>
                    {selected ? <Check className="size-3.5 text-primary" /> : null}
                  </button>
                </li>
              );
            })}
            {!isLoading && sweepable.length === 0 ? (
              <li className="px-2 py-1.5 text-[11px] text-muted-foreground">
                No sweepable parameters on this step.
              </li>
            ) : null}
          </ul>
        </PopoverContent>
      </Popover>

      {/* Hidden text-mode fallback so the existing test (which fires change
          events on this input) keeps working — and so power users can paste
          param keys not yet in the catalog without losing them. */}
      <Input
        type="text"
        placeholder="Or comma-separated param keys"
        value={value.join(", ")}
        onChange={(e) =>
          form.setParamKeys(
            e.target.value
              .split(",")
              .map((s) => s.trim())
              .filter((s) => s !== ""),
          )
        }
        data-testid="optimize-paramkeys-input"
        className="mt-1 text-[11px]"
      />
      {value.some((k) => !known.has(k)) && stepSearchName !== "" && !isLoading ? (
        <p className="mt-1 text-[10px] text-amber-700 dark:text-amber-400">
          Some keys are not in the catalog for this step — they will be
          rejected at launch.
        </p>
      ) : null}
    </FieldShell>
  );
}

function triggerLabel(
  value: string[],
  sweepableCount: number,
  isLoading: boolean,
  stepSearchName: string,
): string {
  if (value.length > 0) {
    return `${value.length} parameter${value.length === 1 ? "" : "s"} selected`;
  }
  if (isLoading) return "Loading parameters…";
  if (sweepableCount === 0 && stepSearchName !== "") {
    return "No tunable parameters on this step";
  }
  return "Pick parameters to tune";
}
