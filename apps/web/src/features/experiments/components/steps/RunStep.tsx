import type { EnrichmentAnalysisType } from "@pathfinder/shared";

const ENRICHMENT_OPTIONS: [EnrichmentAnalysisType, string][] = [
  ["go_function", "GO: Molecular Function"],
  ["go_component", "GO: Cellular Component"],
  ["go_process", "GO: Biological Process"],
  ["pathway", "Metabolic Pathway Enrichment"],
  ["word", "Word Enrichment (Product Descriptions)"],
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
}: RunStepProps) {
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
        </div>
      </div>
    </div>
  );
}
