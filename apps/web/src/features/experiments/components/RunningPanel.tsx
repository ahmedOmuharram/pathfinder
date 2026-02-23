import { FlaskConical, Loader2, X } from "lucide-react";
import { useExperimentStore } from "../store";

export function RunningPanel() {
  const { progress, cancelExperiment } = useExperimentStore();

  const phaseLabel: Record<string, string> = {
    started: "Initializing...",
    optimizing: "Optimizing parameters...",
    evaluating: "Running evaluation...",
    cross_validating: "Cross-validating...",
    enriching: "Running enrichment...",
    completed: "Complete",
    error: "Error",
  };

  return (
    <div className="flex h-full items-center justify-center">
      <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-6 text-center">
        <FlaskConical className="mx-auto h-10 w-10 animate-pulse text-indigo-500" />
        <h2 className="mt-3 text-base font-semibold text-slate-800">
          Running Experiment
        </h2>
        {progress && (
          <div className="mt-3 space-y-2">
            <div className="text-[12px] font-medium text-slate-600">
              {phaseLabel[progress.phase] ?? progress.phase}
            </div>
            {progress.message && (
              <div className="text-[11px] text-slate-500">{progress.message}</div>
            )}
            {progress.cvFoldIndex != null && progress.cvTotalFolds != null && (
              <div className="mx-auto h-1.5 w-48 overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full rounded-full bg-indigo-500 transition-all duration-300"
                  style={{
                    width: `${((progress.cvFoldIndex + 1) / progress.cvTotalFolds) * 100}%`,
                  }}
                />
              </div>
            )}
          </div>
        )}
        {!progress && (
          <div className="mt-3 flex items-center justify-center gap-2 text-[12px] text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Connecting...
          </div>
        )}
        <button
          type="button"
          onClick={cancelExperiment}
          className="mt-4 inline-flex items-center gap-1 rounded-md border border-slate-200 px-3 py-1.5 text-[11px] font-medium text-slate-600 transition hover:border-red-300 hover:bg-red-50 hover:text-red-600"
        >
          <X className="h-3 w-3" />
          Cancel
        </button>
      </div>
    </div>
  );
}
