import type { EnrichmentAnalysisType, OptimizeSpec } from "@pathfinder/shared";
import { Globe, Target } from "lucide-react";

const ENRICHMENT_OPTIONS: [EnrichmentAnalysisType, string][] = [
  ["go_function", "GO: Molecular Function"],
  ["go_component", "GO: Cellular Component"],
  ["go_process", "GO: Biological Process"],
  ["pathway", "Metabolic Pathway Enrichment"],
  ["word", "Word Enrichment (Product Descriptions)"],
];

const OBJECTIVE_OPTIONS: [string, string, string][] = [
  ["balanced_accuracy", "Balanced Accuracy", "(TPR + TNR) / 2"],
  ["f1", "F1 Score", "Harmonic mean of precision & recall"],
  ["recall", "Recall (Sensitivity)", "TP / (TP + FN)"],
  ["precision", "Precision", "TP / (TP + FP)"],
  ["specificity", "Specificity", "TN / (TN + FP)"],
  ["mcc", "MCC", "Matthews Correlation Coefficient"],
  ["youdens_j", "Youden's J", "Sensitivity + Specificity - 1"],
  ["f_beta", "F-beta", "Weighted F-measure"],
];

interface RunStepProps {
  name: string;
  onNameChange: (val: string) => void;
  selectedSearch: string;
  selectedRecordType: string;
  positiveCount: number;
  negativeCount: number;
  enableCV: boolean;
  onEnableCVChange: (val: boolean) => void;
  kFolds: number;
  kFoldsDraft: string;
  onKFoldsChange: (val: number) => void;
  onKFoldsDraftChange: (val: string) => void;
  enrichments: Set<EnrichmentAnalysisType>;
  onToggleEnrichment: (type: EnrichmentAnalysisType) => void;
  optimizeSpecs: Map<string, OptimizeSpec>;
  optimizationBudget: number;
  optimizationBudgetDraft: string;
  onBudgetChange: (val: number) => void;
  onBudgetDraftChange: (val: string) => void;
  optimizationObjective: string;
  onObjectiveChange: (val: string) => void;
  batchMode: boolean;
  onBatchModeChange: (val: boolean) => void;
  batchOrganisms: string[];
  onBatchOrganismsChange: (val: string[]) => void;
  organismOptions: string[];
  organismParamName: string;
  batchOrganismControls: Record<string, { positive: string; negative: string }>;
  onBatchOrganismControlsChange: (
    val: Record<string, { positive: string; negative: string }>,
  ) => void;
}

export function RunStep({
  name,
  onNameChange,
  selectedSearch,
  selectedRecordType,
  positiveCount,
  negativeCount,
  enableCV,
  onEnableCVChange,
  kFolds,
  kFoldsDraft,
  onKFoldsChange,
  onKFoldsDraftChange,
  enrichments,
  onToggleEnrichment,
  optimizeSpecs,
  optimizationBudget,
  optimizationBudgetDraft,
  onBudgetChange,
  onBudgetDraftChange,
  optimizationObjective,
  onObjectiveChange,
  batchMode,
  onBatchModeChange,
  batchOrganisms,
  onBatchOrganismsChange,
  organismOptions,
  organismParamName,
  batchOrganismControls,
  onBatchOrganismControlsChange,
}: RunStepProps) {
  const hasOptimization = optimizeSpecs.size > 0;
  const optimizedParamNames = Array.from(optimizeSpecs.values()).map((s) => s.name);
  const hasBatchCapability = organismOptions.length > 1 && !!organismParamName;

  return (
    <div className="space-y-4">
      <div>
        <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Experiment Name
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder={`${selectedSearch} experiment`}
          className="w-full rounded-md border border-slate-200 px-3 py-2 text-[12px] outline-none placeholder:text-slate-400 focus:border-slate-300"
        />
      </div>

      {/* Optimization config */}
      {hasOptimization && (
        <div className="rounded-md border border-amber-200 bg-amber-50/50 p-3">
          <div className="mb-2 flex items-center gap-1.5">
            <Target className="h-3.5 w-3.5 text-amber-600" />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-amber-700">
              Parameter Optimization
            </span>
          </div>
          <div className="mb-2 text-[11px] text-slate-600">
            Optimizing:{" "}
            <span className="font-medium text-amber-700">
              {optimizedParamNames.join(", ")}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-[10px] text-slate-500">
                Trial Budget
              </label>
              <input
                type="number"
                min={5}
                max={200}
                value={optimizationBudgetDraft}
                onChange={(e) => onBudgetDraftChange(e.target.value)}
                onBlur={() => {
                  const n = parseInt(optimizationBudgetDraft);
                  const clamped = Number.isNaN(n) ? 30 : Math.max(5, Math.min(200, n));
                  onBudgetChange(clamped);
                  onBudgetDraftChange(String(clamped));
                }}
                className="w-full rounded border border-slate-200 px-2 py-1.5 text-[11px] outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-[10px] text-slate-500">
                Objective Metric
              </label>
              <select
                value={optimizationObjective}
                onChange={(e) => onObjectiveChange(e.target.value)}
                className="w-full rounded border border-slate-200 px-2 py-1.5 text-[11px] outline-none"
              >
                {OBJECTIVE_OPTIONS.map(([value, label, desc]) => (
                  <option key={value} value={value} title={desc}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <p className="mt-1.5 text-[10px] text-slate-400">
            {OBJECTIVE_OPTIONS.find(([v]) => v === optimizationObjective)?.[2]}
          </p>
        </div>
      )}

      <div className="rounded-md border border-slate-200 p-3">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={enableCV}
            onChange={(e) => onEnableCVChange(e.target.checked)}
            className="h-3.5 w-3.5 rounded border-slate-300"
          />
          <span className="text-[12px] font-medium text-slate-700">
            Enable Control Robustness Analysis
          </span>
        </label>
        <p className="mt-1 ml-5.5 text-[10px] text-slate-500">
          Evaluates {kFolds} different subsets of your controls to measure consistency.
          Takes ~{kFolds}x longer.
        </p>
        {enableCV && (
          <div className="mt-2 ml-5.5">
            <label className="text-[10px] text-slate-500">Number of folds (k)</label>
            <input
              type="number"
              min={2}
              max={10}
              value={kFoldsDraft}
              onChange={(e) => onKFoldsDraftChange(e.target.value)}
              onBlur={() => {
                const n = parseInt(kFoldsDraft);
                const clamped = Number.isNaN(n) ? 5 : Math.max(2, Math.min(10, n));
                onKFoldsChange(clamped);
                onKFoldsDraftChange(String(clamped));
              }}
              className="ml-2 w-16 rounded border border-slate-200 px-2 py-1 text-[11px] outline-none"
            />
          </div>
        )}
      </div>

      <div className="rounded-md border border-slate-200 p-3">
        <label className="mb-2 block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Enrichment Analyses
        </label>
        <div className="space-y-1.5">
          {ENRICHMENT_OPTIONS.map(([type, label]) => (
            <label key={type} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={enrichments.has(type)}
                onChange={() => onToggleEnrichment(type)}
                className="h-3.5 w-3.5 rounded border-slate-300"
              />
              <span className="text-[12px] text-slate-700">{label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Batch mode */}
      {hasBatchCapability && (
        <div className="rounded-md border border-slate-200 p-3">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={batchMode}
              onChange={(e) => onBatchModeChange(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-slate-300"
            />
            <Globe className="h-3.5 w-3.5 text-slate-500" />
            <span className="text-[12px] font-medium text-slate-700">
              Batch Mode — Run Across Multiple Organisms
            </span>
          </label>
          <p className="mt-1 ml-5.5 text-[10px] text-slate-500">
            Run the same search with the same controls across multiple organisms in
            parallel. Each organism produces its own experiment.
          </p>

          {batchMode && (
            <div className="mt-3 space-y-2">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Select organisms ({batchOrganisms.length} selected)
              </div>
              <div className="max-h-48 overflow-y-auto rounded-md border border-slate-200 bg-white">
                {organismOptions.map((org) => {
                  const checked = batchOrganisms.includes(org);
                  return (
                    <label
                      key={org}
                      className="flex items-center gap-2 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-50"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => {
                          const next = checked
                            ? batchOrganisms.filter((o) => o !== org)
                            : [...batchOrganisms, org];
                          onBatchOrganismsChange(next);
                        }}
                        className="h-3 w-3 rounded border-slate-300"
                      />
                      {org}
                    </label>
                  );
                })}
              </div>

              {batchOrganisms.length > 0 && (
                <div className="mt-2 space-y-2">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    Per-organism control overrides (optional)
                  </div>
                  {batchOrganisms.map((org) => {
                    const ctrls = batchOrganismControls[org] ?? {
                      positive: "",
                      negative: "",
                    };
                    return (
                      <div
                        key={org}
                        className="rounded border border-slate-100 bg-slate-50 p-2"
                      >
                        <div className="mb-1 text-[11px] font-medium text-slate-700">
                          {org}
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <input
                            type="text"
                            value={ctrls.positive}
                            onChange={(e) =>
                              onBatchOrganismControlsChange({
                                ...batchOrganismControls,
                                [org]: { ...ctrls, positive: e.target.value },
                              })
                            }
                            placeholder="Positive genes (comma-sep)"
                            className="rounded border border-slate-200 px-2 py-1 text-[10px] outline-none placeholder:text-slate-400"
                          />
                          <input
                            type="text"
                            value={ctrls.negative}
                            onChange={(e) =>
                              onBatchOrganismControlsChange({
                                ...batchOrganismControls,
                                [org]: { ...ctrls, negative: e.target.value },
                              })
                            }
                            placeholder="Negative genes (comma-sep)"
                            className="rounded border border-slate-200 px-2 py-1 text-[10px] outline-none placeholder:text-slate-400"
                          />
                        </div>
                      </div>
                    );
                  })}
                  <p className="text-[10px] text-slate-400">
                    Leave empty to use the default positive/negative controls.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="rounded-md border border-indigo-200 bg-indigo-50/50 p-3">
        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-indigo-700">
          Summary
        </div>
        <div className="space-y-0.5 text-[11px] text-slate-600">
          <div>
            Search: <span className="font-medium">{selectedSearch}</span>
          </div>
          <div>
            Record type: <span className="font-medium">{selectedRecordType}</span>
          </div>
          <div>
            Positive controls: <span className="font-medium">{positiveCount}</span>
          </div>
          <div>
            Negative controls: <span className="font-medium">{negativeCount}</span>
          </div>
          {hasOptimization && (
            <div>
              Optimization:{" "}
              <span className="font-medium">
                {optimizeSpecs.size} params, {optimizationBudget} trials (
                {optimizationObjective})
              </span>
            </div>
          )}
          {enableCV && (
            <div>
              Robustness analysis: <span className="font-medium">{kFolds} subsets</span>
            </div>
          )}
          {enrichments.size > 0 && (
            <div>
              Enrichment:{" "}
              <span className="font-medium">{enrichments.size} analyses</span>
            </div>
          )}
          {batchMode && batchOrganisms.length > 0 && (
            <div>
              Batch:{" "}
              <span className="font-medium">{batchOrganisms.length} organisms</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
