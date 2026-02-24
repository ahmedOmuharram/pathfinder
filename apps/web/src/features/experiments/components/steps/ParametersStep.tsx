import type { OptimizeSpec, ParamSpec } from "@pathfinder/shared";
import { Info } from "lucide-react";
import { Label } from "@/lib/components/ui/Label";
import { Input } from "@/lib/components/ui/Input";
import { Button } from "@/lib/components/ui/Button";
import { Skeleton } from "@/lib/components/ui/Skeleton";
import { Separator } from "@/lib/components/ui/Separator";
import { ParamField } from "../ParamField";

interface ParametersStepProps {
  selectedSearch: string;
  paramSpecs: ParamSpec[];
  paramSpecsLoading: boolean;
  parameters: Record<string, string>;
  onParameterChange: (name: string, value: string) => void;
  onParametersReplace: (
    fn: (prev: Record<string, string>) => Record<string, string>,
  ) => void;
  optimizeSpecs: Record<string, OptimizeSpec>;
  onOptimizeSpecChange: (name: string, spec: OptimizeSpec | null) => void;
  showValidation: boolean;
}

export function ParametersStep({
  selectedSearch,
  paramSpecs,
  paramSpecsLoading,
  parameters,
  onParameterChange,
  onParametersReplace,
  optimizeSpecs,
  onOptimizeSpecChange,
  showValidation,
}: ParametersStepProps) {
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <Label>
          Parameters for:{" "}
          <span className="font-mono font-semibold text-foreground">
            {selectedSearch}
          </span>
        </Label>
      </div>

      {paramSpecsLoading && (
        <div className="space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-3/4" />
        </div>
      )}

      {!paramSpecsLoading && paramSpecs.length === 0 && (
        <div className="rounded-lg border border-border bg-muted/50 p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Info className="h-4 w-4 shrink-0" />
            <span>
              {selectedSearch
                ? "No configurable parameters found for this search."
                : "Select a search first to see its parameters."}
            </span>
          </div>
        </div>
      )}

      {paramSpecs.length > 0 && (
        <div className="space-y-3">
          {paramSpecs.map((spec) => (
            <ParamField
              key={spec.name}
              spec={spec}
              value={parameters[spec.name] ?? ""}
              onChange={(val) => onParameterChange(spec.name, val)}
              optimizeSpec={optimizeSpecs[spec.name] ?? null}
              onOptimizeChange={(os) => onOptimizeSpecChange(spec.name, os)}
              showValidation={showValidation}
            />
          ))}
        </div>
      )}

      <Separator />

      <div>
        <div className="flex items-center justify-between">
          <Label className="text-muted-foreground">Custom parameters</Label>
          <Button
            variant="link"
            size="sm"
            className="h-auto p-0 text-xs"
            onClick={() => {
              const key = prompt("Parameter name:");
              if (key && !paramSpecs.some((s) => s.name === key)) {
                onParameterChange(key, "");
              }
            }}
          >
            + Add custom parameter
          </Button>
        </div>
        {Object.entries(parameters)
          .filter(([key]) => !paramSpecs.some((s) => s.name === key))
          .map(([key, val]) => (
            <div key={key} className="mt-2 flex items-center gap-2">
              <span className="w-1/3 truncate rounded-md border border-border bg-muted px-2 py-1.5 text-xs font-mono text-muted-foreground">
                {key}
              </span>
              <Input
                type="text"
                value={val}
                onChange={(e) => onParameterChange(key, e.target.value)}
                className="flex-1"
              />
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:text-destructive"
                onClick={() =>
                  onParametersReplace((p) => {
                    const next = { ...p };
                    delete next[key];
                    return next;
                  })
                }
              >
                Remove
              </Button>
            </div>
          ))}
      </div>
    </div>
  );
}
