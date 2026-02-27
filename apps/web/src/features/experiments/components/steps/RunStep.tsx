import type { EnrichmentAnalysisType, OptimizeSpec } from "@pathfinder/shared";
import { Globe, Target } from "lucide-react";
import { Label } from "@/lib/components/ui/Label";
import { Input } from "@/lib/components/ui/Input";
import { Card, CardContent } from "@/lib/components/ui/Card";
import { Badge } from "@/lib/components/ui/Badge";
import { cn } from "@/lib/utils/cn";

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
    <div className="space-y-5">
      <div>
        <Label className="mb-1.5 block">Experiment Name</Label>
        <Input
          type="text"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder={`${selectedSearch} experiment`}
        />
      </div>

      {hasOptimization && (
        <Card className="border-warning/30 bg-warning/5">
          <CardContent className="p-4">
            <div className="mb-3 flex items-center gap-1.5">
              <Target className="h-4 w-4 text-warning" />
              <span className="text-sm font-semibold text-warning">
                Parameter Optimization
              </span>
            </div>
            <div className="mb-3 text-sm text-muted-foreground">
              Optimizing:{" "}
              <span className="font-medium font-mono text-foreground">
                {optimizedParamNames.join(", ")}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="mb-1 block text-xs">Trial Budget</Label>
                <Input
                  type="number"
                  min={5}
                  max={200}
                  value={optimizationBudgetDraft}
                  onChange={(e) => onBudgetDraftChange(e.target.value)}
                  onBlur={() => {
                    const n = parseInt(optimizationBudgetDraft);
                    const clamped = Number.isNaN(n)
                      ? 30
                      : Math.max(5, Math.min(200, n));
                    onBudgetChange(clamped);
                    onBudgetDraftChange(String(clamped));
                  }}
                />
              </div>
              <div>
                <Label className="mb-1 block text-xs">Objective Metric</Label>
                <select
                  value={optimizationObjective}
                  onChange={(e) => onObjectiveChange(e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  {OBJECTIVE_OPTIONS.map(([value, label, desc]) => (
                    <option key={value} value={value} title={desc}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              {OBJECTIVE_OPTIONS.find(([v]) => v === optimizationObjective)?.[2]}
            </p>
          </CardContent>
        </Card>
      )}

      {hasOptimization && (
        <Card>
          <CardContent className="p-4">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={enableCV}
                onChange={(e) => onEnableCVChange(e.target.checked)}
                className="h-4 w-4 rounded border-input"
              />
              <span className="text-sm font-medium text-foreground">
                Enable Control Robustness Analysis
              </span>
            </label>
            <p className="mt-1.5 ml-6 text-xs text-muted-foreground">
              Evaluates {kFolds} different subsets of your controls to measure
              consistency. Takes ~{kFolds}x longer.
            </p>
            {enableCV && (
              <div className="mt-2 ml-6 flex items-center gap-2">
                <Label className="text-xs">Number of folds (k)</Label>
                <Input
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
                  className="w-16"
                />
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {hasOptimization && (
        <Card>
          <CardContent className="p-4">
            <Label className="mb-3 block">Enrichment Analyses</Label>
            <div className="space-y-2">
              {ENRICHMENT_OPTIONS.map(([type, label]) => (
                <label key={type} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={enrichments.has(type)}
                    onChange={() => onToggleEnrichment(type)}
                    className="h-4 w-4 rounded border-input"
                  />
                  <span className="text-sm text-foreground">{label}</span>
                </label>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {hasBatchCapability && (
        <Card>
          <CardContent className="p-4">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={batchMode}
                onChange={(e) => onBatchModeChange(e.target.checked)}
                className="h-4 w-4 rounded border-input"
              />
              <Globe className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium text-foreground">
                Batch Mode -- Run Across Multiple Organisms
              </span>
            </label>
            <p className="mt-1.5 ml-6 text-xs text-muted-foreground">
              Run the same search with the same controls across multiple organisms in
              parallel. Each organism produces its own experiment.
            </p>

            {batchMode && (
              <div className="mt-3 space-y-3">
                <div className="text-xs font-medium text-muted-foreground">
                  Select organisms ({batchOrganisms.length} selected)
                </div>
                <div className="max-h-48 overflow-y-auto rounded-lg border border-border bg-background">
                  {organismOptions.map((org) => {
                    const checked = batchOrganisms.includes(org);
                    return (
                      <label
                        key={org}
                        className={cn(
                          "flex items-center gap-2 px-3 py-1.5 text-sm text-foreground transition-colors duration-150 hover:bg-accent",
                          checked && "bg-accent/50",
                        )}
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
                          className="h-3.5 w-3.5 rounded border-input"
                        />
                        {org}
                      </label>
                    );
                  })}
                </div>

                {batchOrganisms.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-xs font-medium text-muted-foreground">
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
                          className="rounded-lg border border-border bg-muted/50 p-3"
                        >
                          <div className="mb-1.5 text-sm font-medium text-foreground">
                            {org}
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <Input
                              type="text"
                              value={ctrls.positive}
                              onChange={(e) =>
                                onBatchOrganismControlsChange({
                                  ...batchOrganismControls,
                                  [org]: { ...ctrls, positive: e.target.value },
                                })
                              }
                              placeholder="Positive genes (comma-sep)"
                            />
                            <Input
                              type="text"
                              value={ctrls.negative}
                              onChange={(e) =>
                                onBatchOrganismControlsChange({
                                  ...batchOrganismControls,
                                  [org]: { ...ctrls, negative: e.target.value },
                                })
                              }
                              placeholder="Negative genes (comma-sep)"
                            />
                          </div>
                        </div>
                      );
                    })}
                    <p className="text-xs text-muted-foreground">
                      Leave empty to use the default positive/negative controls.
                    </p>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card className="border-primary/20 bg-primary/5">
        <CardContent className="p-4">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-primary">
            Summary
          </div>
          <div className="space-y-1 text-sm text-muted-foreground">
            <div>
              Search:{" "}
              <span className="font-medium font-mono text-foreground">
                {selectedSearch}
              </span>
            </div>
            <div>
              Record type:{" "}
              <Badge variant="outline" className="ml-1 text-xs">
                {selectedRecordType}
              </Badge>
            </div>
            <div>
              Positive controls:{" "}
              <span className="font-medium text-foreground">{positiveCount}</span>
            </div>
            <div>
              Negative controls:{" "}
              <span className="font-medium text-foreground">{negativeCount}</span>
            </div>
            {hasOptimization && (
              <div>
                Optimization:{" "}
                <span className="font-medium text-foreground">
                  {optimizeSpecs.size} params, {optimizationBudget} trials (
                  {optimizationObjective})
                </span>
              </div>
            )}
            {enableCV && (
              <div>
                Robustness analysis:{" "}
                <span className="font-medium text-foreground">{kFolds} subsets</span>
              </div>
            )}
            {enrichments.size > 0 && (
              <div>
                Enrichment:{" "}
                <span className="font-medium text-foreground">
                  {enrichments.size} analyses
                </span>
              </div>
            )}
            {batchMode && batchOrganisms.length > 0 && (
              <div>
                Batch:{" "}
                <span className="font-medium text-foreground">
                  {batchOrganisms.length} organisms
                </span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
