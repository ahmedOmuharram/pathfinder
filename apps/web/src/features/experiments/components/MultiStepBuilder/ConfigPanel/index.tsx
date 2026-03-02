import type {
  EnrichmentAnalysisType,
  ThresholdKnob,
  OperatorKnob,
  ResolvedGene,
} from "@pathfinder/shared";
import type { RecordAttribute } from "../../../api/crud";
import type { BenchmarkControlSetInput } from "../../../api/streaming";
import { Button } from "@/lib/components/ui/Button";
import { AlertTriangle, BarChart3, FlaskConical } from "lucide-react";
import { ControlsSection } from "./ControlsSection";
import { EnrichmentConfigSection } from "./EnrichmentConfigSection";
import { OptimizationSection } from "./OptimizationSection";
import { StepAnalysisSection, type StepAnalysisConfig } from "./StepAnalysisSection";
import { SortingSection } from "./SortingSection";

/* ── Public types ─────────────────────────────────────────────────── */

export type { StepAnalysisConfig };

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

  stepAnalysis: StepAnalysisConfig;
  onStepAnalysisChange: (v: StepAnalysisConfig) => void;

  thresholdKnobs: ThresholdKnob[];
  onThresholdKnobsChange: (v: ThresholdKnob[]) => void;
  operatorKnobs: OperatorKnob[];
  onOperatorKnobsChange: (v: OperatorKnob[]) => void;
  treeOptObjective: string;
  onTreeOptObjectiveChange: (v: string) => void;

  sortAttribute: string | null;
  onSortAttributeChange: (v: string | null) => void;
  sortDirection: "ASC" | "DESC";
  onSortDirectionChange: (v: "ASC" | "DESC") => void;
  sortableAttributes: RecordAttribute[];

  benchmarkMode: boolean;
  onBenchmarkModeChange: (v: boolean) => void;
  benchmarkControlSets: BenchmarkControlSetInput[];
  onBenchmarkControlSetsChange: (v: BenchmarkControlSetInput[]) => void;

  warnings: { stepId: string; message: string; severity: "warning" | "error" }[];
  canRun: boolean;
  isRunning: boolean;
  storeError: string | null;
  onRun: () => void;
}

/* ── ConfigPanel ──────────────────────────────────────────────────── */

export function ConfigPanel(props: ConfigPanelProps) {
  const {
    siteId,
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
    stepAnalysis,
    onStepAnalysisChange,
    thresholdKnobs,
    onThresholdKnobsChange,
    operatorKnobs,
    onOperatorKnobsChange,
    treeOptObjective,
    onTreeOptObjectiveChange,
    sortAttribute,
    onSortAttributeChange,
    sortDirection,
    onSortDirectionChange,
    sortableAttributes,
    benchmarkMode,
    onBenchmarkModeChange,
    benchmarkControlSets,
    onBenchmarkControlSetsChange,
    warnings,
    canRun,
    isRunning,
    storeError,
    onRun,
  } = props;

  return (
    <div
      data-testid="config-panel"
      className="flex h-full flex-col overflow-y-auto border-l border-border bg-sidebar"
    >
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
        <ControlsSection
          siteId={siteId}
          positiveGenes={positiveGenes}
          onPositiveGenesChange={onPositiveGenesChange}
          negativeGenes={negativeGenes}
          onNegativeGenesChange={onNegativeGenesChange}
          onOpenControlsModal={onOpenControlsModal}
          benchmarkMode={benchmarkMode}
          onBenchmarkModeChange={onBenchmarkModeChange}
          benchmarkControlSets={benchmarkControlSets}
          onBenchmarkControlSetsChange={onBenchmarkControlSetsChange}
        />

        {/* Step Analysis */}
        <StepAnalysisSection
          stepAnalysis={stepAnalysis}
          onStepAnalysisChange={onStepAnalysisChange}
        />

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
        <EnrichmentConfigSection
          enrichments={enrichments}
          onToggleEnrichment={onToggleEnrichment}
        />

        {/* Tree Optimization Knobs */}
        <OptimizationSection
          thresholdKnobs={thresholdKnobs}
          onThresholdKnobsChange={onThresholdKnobsChange}
          operatorKnobs={operatorKnobs}
          onOperatorKnobsChange={onOperatorKnobsChange}
          treeOptObjective={treeOptObjective}
          onTreeOptObjectiveChange={onTreeOptObjectiveChange}
        />

        {/* Ranking */}
        <SortingSection
          sortAttribute={sortAttribute}
          onSortAttributeChange={onSortAttributeChange}
          sortDirection={sortDirection}
          onSortDirectionChange={onSortDirectionChange}
          sortableAttributes={sortableAttributes}
        />

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
          data-testid="run-experiment-btn"
          className="w-full"
          onClick={onRun}
          disabled={!canRun || isRunning}
          loading={isRunning}
        >
          {!isRunning &&
            (stepAnalysis.enabled ? (
              <FlaskConical className="h-3.5 w-3.5" />
            ) : (
              <BarChart3 className="h-3.5 w-3.5" />
            ))}
          {isRunning
            ? stepAnalysis.enabled
              ? "Analyzing..."
              : "Evaluating..."
            : stepAnalysis.enabled
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
