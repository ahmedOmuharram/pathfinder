import type { OptimizeSpec, ParamSpec } from "@pathfinder/shared";
import { Info, Loader2 } from "lucide-react";
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
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Parameters for:{" "}
          <span className="normal-case font-bold text-slate-700">{selectedSearch}</span>
        </label>
        {paramSpecsLoading && (
          <div className="flex items-center gap-1 text-[10px] text-slate-400">
            <Loader2 className="h-3 w-3 animate-spin" /> Loading...
          </div>
        )}
      </div>

      {!paramSpecsLoading && paramSpecs.length === 0 && (
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center gap-2 text-[11px] text-slate-600">
            <Info className="h-3.5 w-3.5 text-slate-400" />
            <span>
              {selectedSearch
                ? "No configurable parameters found for this search, or parameters could not be loaded."
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

      <div className="border-t border-slate-200 pt-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Custom parameters
          </span>
          <button
            type="button"
            onClick={() => {
              const key = prompt("Parameter name:");
              if (key && !paramSpecs.some((s) => s.name === key)) {
                onParameterChange(key, "");
              }
            }}
            className="text-[11px] font-medium text-indigo-600"
          >
            + Add custom parameter
          </button>
        </div>
        {Object.entries(parameters)
          .filter(([key]) => !paramSpecs.some((s) => s.name === key))
          .map(([key, val]) => (
            <div key={key} className="mt-2 flex items-center gap-2">
              <span className="w-1/3 truncate rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 text-[11px] text-slate-600">
                {key}
              </span>
              <input
                type="text"
                value={val}
                onChange={(e) => onParameterChange(key, e.target.value)}
                className="flex-1 rounded-md border border-slate-200 px-2 py-1.5 text-[12px] outline-none focus:border-slate-300"
              />
              <button
                type="button"
                onClick={() =>
                  onParametersReplace((p) => {
                    const next = { ...p };
                    delete next[key];
                    return next;
                  })
                }
                className="text-[11px] text-red-500 hover:text-red-700"
              >
                Remove
              </button>
            </div>
          ))}
      </div>
    </div>
  );
}
