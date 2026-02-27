import type { EnrichmentAnalysisType } from "@pathfinder/shared";
import type { ResolvedGene } from "@/lib/api/client";
import { Button } from "@/lib/components/ui/Button";
import {
  AlertTriangle,
  BarChart3,
  FlaskConical,
  Search,
  Sparkles,
  X,
} from "lucide-react";

export interface TreeOptimizationConfig {
  enabled: boolean;
  budget: number;
  objective: string;
  optimizeOperators: boolean;
  optimizeOrthologs: boolean;
  optimizeStructure: boolean;
}

interface ConfigPanelProps {
  siteId: string;
  name: string;
  onNameChange: (v: string) => void;

  positiveGenes: ResolvedGene[];
  onPositiveGenesChange: (genes: ResolvedGene[]) => void;
  negativeGenes: ResolvedGene[];
  onNegativeGenesChange: (genes: ResolvedGene[]) => void;
  onOpenControlsModal: () => void;

  enableCV: boolean;
  onEnableCVChange: (v: boolean) => void;
  kFolds: number;
  kFoldsDraft: string;
  onKFoldsChange: (v: number) => void;
  onKFoldsDraftChange: (v: string) => void;

  enrichments: Set<EnrichmentAnalysisType>;
  onToggleEnrichment: (type: EnrichmentAnalysisType) => void;

  treeOpt: TreeOptimizationConfig;
  onTreeOptChange: (v: TreeOptimizationConfig) => void;

  warnings: { stepId: string; message: string; severity: "warning" | "error" }[];
  canRun: boolean;
  isRunning: boolean;
  storeError: string | null;
  onRun: () => void;
}

const ENRICHMENT_OPTIONS: { type: EnrichmentAnalysisType; label: string }[] = [
  { type: "go_function", label: "GO: Molecular Function" },
  { type: "go_component", label: "GO: Cellular Component" },
  { type: "go_process", label: "GO: Biological Process" },
  { type: "pathway", label: "Metabolic Pathway" },
  { type: "word", label: "Word Enrichment" },
];

const OBJECTIVE_OPTIONS = [
  { value: "balanced_accuracy", label: "Balanced Accuracy" },
  { value: "f1", label: "F1 Score" },
  { value: "sensitivity", label: "Sensitivity (Recall)" },
  { value: "specificity", label: "Specificity" },
  { value: "mcc", label: "MCC" },
];

export function ConfigPanel(props: ConfigPanelProps) {
  const {
    name,
    onNameChange,
    positiveGenes,
    onPositiveGenesChange,
    negativeGenes,
    onNegativeGenesChange,
    onOpenControlsModal,
    enableCV,
    onEnableCVChange,
    kFolds,
    kFoldsDraft,
    onKFoldsChange,
    onKFoldsDraftChange,
    enrichments,
    onToggleEnrichment,
    treeOpt,
    onTreeOptChange,
    warnings,
    canRun,
    isRunning,
    storeError,
    onRun,
  } = props;

  const budgetDraft = String(treeOpt.budget);

  return (
    <div className="flex h-full flex-col overflow-y-auto border-l border-border bg-sidebar">
      <div className="border-b border-border p-4">
        <h3 className="text-sm font-semibold text-foreground">Configuration</h3>
      </div>

      <div className="flex-1 space-y-5 p-4">
        {/* Name */}
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">
            Experiment Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="Multi-step experiment"
            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
          />
        </div>

        {/* Controls */}
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Controls
          </h4>

          <Button
            variant="outline"
            size="sm"
            className="mb-2 w-full border-dashed"
            onClick={onOpenControlsModal}
          >
            <Search className="h-3 w-3" />
            {positiveGenes.length + negativeGenes.length > 0
              ? "Edit Control Genes"
              : "Find Control Genes"}
          </Button>

          {positiveGenes.length > 0 && (
            <div className="mb-2">
              <label className="mb-1 block text-[10px] text-muted-foreground">
                Positive ({positiveGenes.length})
              </label>
              <div className="flex flex-wrap gap-1">
                {positiveGenes.slice(0, 8).map((g) => (
                  <span
                    key={g.geneId}
                    className="inline-flex items-center gap-1 rounded bg-green-500/10 px-1.5 py-0.5 text-[10px] text-green-700 dark:text-green-400"
                  >
                    {g.geneId}
                    <button
                      onClick={() =>
                        onPositiveGenesChange(
                          positiveGenes.filter((x) => x.geneId !== g.geneId),
                        )
                      }
                      className="hover:text-destructive"
                    >
                      <X className="h-2.5 w-2.5" />
                    </button>
                  </span>
                ))}
                {positiveGenes.length > 8 && (
                  <span className="text-[10px] text-muted-foreground">
                    +{positiveGenes.length - 8} more
                  </span>
                )}
              </div>
            </div>
          )}

          {negativeGenes.length > 0 && (
            <div>
              <label className="mb-1 block text-[10px] text-muted-foreground">
                Negative ({negativeGenes.length})
              </label>
              <div className="flex flex-wrap gap-1">
                {negativeGenes.slice(0, 8).map((g) => (
                  <span
                    key={g.geneId}
                    className="inline-flex items-center gap-1 rounded bg-red-500/10 px-1.5 py-0.5 text-[10px] text-red-700 dark:text-red-400"
                  >
                    {g.geneId}
                    <button
                      onClick={() =>
                        onNegativeGenesChange(
                          negativeGenes.filter((x) => x.geneId !== g.geneId),
                        )
                      }
                      className="hover:text-destructive"
                    >
                      <X className="h-2.5 w-2.5" />
                    </button>
                  </span>
                ))}
                {negativeGenes.length > 8 && (
                  <span className="text-[10px] text-muted-foreground">
                    +{negativeGenes.length - 8} more
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Tree Optimization */}
        <div>
          <label className="flex items-center gap-2 text-xs font-medium text-foreground">
            <input
              type="checkbox"
              checked={treeOpt.enabled}
              onChange={(e) =>
                onTreeOptChange({ ...treeOpt, enabled: e.target.checked })
              }
              className="rounded border-input"
            />
            <Sparkles className="h-3 w-3 text-primary" />
            Optimize Strategy Tree
          </label>
          <p className="mt-0.5 pl-5 text-[10px] text-muted-foreground">
            Mutate parameters and operators across the entire tree to maximise control
            gene recovery.
          </p>

          {treeOpt.enabled && (
            <div className="mt-2 space-y-2 pl-5">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="mb-0.5 block text-[10px] text-muted-foreground">
                    Budget (trials)
                  </label>
                  <input
                    type="number"
                    min={5}
                    max={100}
                    value={budgetDraft}
                    onChange={(e) => {
                      const n = parseInt(e.target.value, 10);
                      if (!isNaN(n) && n >= 5 && n <= 100) {
                        onTreeOptChange({ ...treeOpt, budget: n });
                      }
                    }}
                    className="w-full rounded border border-input bg-background px-2 py-1 text-xs focus:border-primary focus:outline-none"
                  />
                </div>
                <div>
                  <label className="mb-0.5 block text-[10px] text-muted-foreground">
                    Objective
                  </label>
                  <select
                    value={treeOpt.objective}
                    onChange={(e) =>
                      onTreeOptChange({ ...treeOpt, objective: e.target.value })
                    }
                    className="w-full rounded border border-input bg-background px-2 py-1 text-xs focus:border-primary focus:outline-none"
                  >
                    {OBJECTIVE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <label className="flex items-center gap-2 text-xs text-foreground">
                <input
                  type="checkbox"
                  checked={treeOpt.optimizeOperators}
                  onChange={(e) =>
                    onTreeOptChange({
                      ...treeOpt,
                      optimizeOperators: e.target.checked,
                    })
                  }
                  className="rounded border-input"
                />
                Optimize boolean operators
              </label>

              <label className="flex items-center gap-2 text-xs text-foreground">
                <input
                  type="checkbox"
                  checked={treeOpt.optimizeOrthologs}
                  onChange={(e) =>
                    onTreeOptChange({
                      ...treeOpt,
                      optimizeOrthologs: e.target.checked,
                    })
                  }
                  className="rounded border-input"
                />
                Try ortholog transforms
              </label>

              <label className="flex items-center gap-2 text-xs text-foreground">
                <input
                  type="checkbox"
                  checked={treeOpt.optimizeStructure}
                  onChange={(e) =>
                    onTreeOptChange({
                      ...treeOpt,
                      optimizeStructure: e.target.checked,
                    })
                  }
                  className="rounded border-input"
                />
                AI structural analysis
              </label>
              {treeOpt.optimizeStructure && (
                <p className="pl-5 text-[10px] text-muted-foreground">
                  An LLM will propose structural changes (add/remove/swap steps) that
                  Optuna will evaluate alongside parameter tuning.
                </p>
              )}
            </div>
          )}
        </div>

        {treeOpt.enabled && (
          <>
            {/* Cross-validation */}
            <div>
              <label className="flex items-center gap-2 text-xs text-foreground">
                <input
                  type="checkbox"
                  checked={enableCV}
                  onChange={(e) => onEnableCVChange(e.target.checked)}
                  className="rounded border-input"
                />
                Cross-Validation
              </label>
              {enableCV && (
                <div className="mt-1 flex items-center gap-2">
                  <label className="text-[10px] text-muted-foreground">K-Folds:</label>
                  <input
                    type="text"
                    value={kFoldsDraft}
                    onChange={(e) => onKFoldsDraftChange(e.target.value)}
                    onBlur={() => {
                      const n = parseInt(kFoldsDraft, 10);
                      if (!isNaN(n) && n >= 2) onKFoldsChange(n);
                      else onKFoldsDraftChange(String(kFolds));
                    }}
                    className="w-14 rounded border border-input bg-background px-2 py-0.5 text-xs focus:border-primary focus:outline-none"
                  />
                </div>
              )}
            </div>

            {/* Enrichment */}
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Enrichment
              </h4>
              <div className="space-y-1">
                {ENRICHMENT_OPTIONS.map((opt) => (
                  <label
                    key={opt.type}
                    className="flex items-center gap-2 text-xs text-foreground"
                  >
                    <input
                      type="checkbox"
                      checked={enrichments.has(opt.type)}
                      onChange={() => onToggleEnrichment(opt.type)}
                      className="rounded border-input"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>
          </>
        )}

        {/* Warnings */}
        {warnings.length > 0 && (
          <div className="space-y-1">
            {warnings.map((w, i) => (
              <div
                key={i}
                className={`flex items-start gap-2 rounded-md border px-2 py-1.5 text-xs ${
                  w.severity === "error"
                    ? "border-destructive/30 bg-destructive/5 text-destructive"
                    : "border-yellow-500/30 bg-yellow-500/5 text-yellow-700 dark:text-yellow-400"
                }`}
              >
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                {w.message}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Error */}
      {storeError && (
        <div className="border-t border-destructive/30 bg-destructive/5 px-4 py-2 text-xs text-destructive">
          <span className="font-semibold">Error:</span> {storeError}
        </div>
      )}

      {/* Run Button */}
      <div className="border-t border-border p-4">
        <Button
          className="w-full"
          onClick={onRun}
          disabled={!canRun || isRunning}
          loading={isRunning}
        >
          {!isRunning &&
            (treeOpt.enabled ? (
              <FlaskConical className="h-3.5 w-3.5" />
            ) : (
              <BarChart3 className="h-3.5 w-3.5" />
            ))}
          {isRunning
            ? treeOpt.enabled
              ? "Optimizing..."
              : "Evaluating..."
            : treeOpt.enabled
              ? "Run Experiment"
              : "Evaluate Strategy"}
        </Button>
        {!canRun && !isRunning && (
          <p className="mt-1 text-center text-[10px] text-muted-foreground">
            {positiveGenes.length === 0 && negativeGenes.length === 0
              ? "Add control genes to continue"
              : "Build a valid strategy graph to continue"}
          </p>
        )}
      </div>
    </div>
  );
}
