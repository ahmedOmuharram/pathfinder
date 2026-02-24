import { ArrowLeft, ArrowRight, FlaskConical, Loader2 } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { Stepper } from "@/lib/components/ui/Stepper";
import { AiAssistantPanel } from "../AiAssistantPanel";
import { SearchStep } from "../steps/SearchStep";
import { ParametersStep } from "../steps/ParametersStep";
import { ControlsStep } from "../steps/ControlsStep";
import { RunStep } from "../steps/RunStep";
import { useSetupWizard } from "./useSetupWizard";
import { STEPS } from "./constants";

interface SetupWizardProps {
  siteId: string;
}

export function SetupWizard({ siteId }: SetupWizardProps) {
  const wizard = useSetupWizard(siteId);

  const {
    step,
    setStep,
    attemptedSteps,
    recordTypes,
    selectedRecordType,
    filteredSearches,
    searchFilter,
    setSearchFilter,
    selectedSearch,
    setSelectedSearch,
    paramSpecs: _paramSpecs,
    paramSpecsLoading,
    parameters,
    setParameters,
    visibleParamSpecs,
    positiveGenes,
    setPositiveGenes,
    negativeGenes,
    setNegativeGenes,
    showGeneLookup,
    setShowGeneLookup,
    currentAiStep,
    aiContext,
    name,
    setName,
    enableCV,
    setEnableCV,
    kFolds,
    kFoldsDraft,
    setKFolds,
    setKFoldsDraft,
    enrichments,
    positiveControls,
    negativeControls,
    isTransformSearch,
    stepValidation,
    storeError,
    isRunning,
    handleRecordTypeChange,
    handleSuggestionApply,
    handleGeneAdd,
    handleParamsApply,
    handleRunConfigApply,
    handleParameterChange,
    handleOptimizeChange,
    toggleEnrichment,
    goBack,
    goNext,
    runOrValidate,
    canNext,
    optimizeSpecs,
    optimizationBudget,
    optimizationBudgetDraft,
    setOptimizationBudget,
    setOptimizationBudgetDraft,
    optimizationObjective,
    setOptimizationObjective,
    batchMode,
    setBatchMode,
    batchOrganisms,
    setBatchOrganisms,
    batchOrganismControls,
    setBatchOrganismControls,
    organismParamName,
    organismOptions,
  } = wizard;

  return (
    <div className="flex h-full">
      <div className="flex flex-1 flex-col p-6">
        <Stepper
          steps={[...STEPS]}
          currentStep={step}
          onStepClick={(i) => i <= step && setStep(i)}
          className="mb-6"
        />

        <div className="min-h-0 flex-1 overflow-y-auto animate-fade-in" key={step}>
          {step === 0 && (
            <SearchStep
              recordTypes={recordTypes}
              selectedRecordType={selectedRecordType}
              onRecordTypeChange={handleRecordTypeChange}
              filteredSearches={filteredSearches}
              searchFilter={searchFilter}
              onSearchFilterChange={setSearchFilter}
              selectedSearch={selectedSearch}
              onSearchChange={setSelectedSearch}
            />
          )}
          {step === 1 && (
            <ParametersStep
              selectedSearch={selectedSearch}
              paramSpecs={visibleParamSpecs}
              paramSpecsLoading={paramSpecsLoading}
              parameters={parameters}
              onParameterChange={handleParameterChange}
              onParametersReplace={setParameters}
              optimizeSpecs={Object.fromEntries(optimizeSpecs)}
              onOptimizeSpecChange={handleOptimizeChange}
              showValidation={attemptedSteps.has(1)}
            />
          )}
          {step === 2 && (
            <ControlsStep
              siteId={siteId}
              positiveGenes={positiveGenes}
              onPositiveGenesChange={setPositiveGenes}
              negativeGenes={negativeGenes}
              onNegativeGenesChange={setNegativeGenes}
              showGeneLookup={showGeneLookup}
              onShowGeneLookupChange={setShowGeneLookup}
              isTransformSearch={isTransformSearch}
            />
          )}
          {step === 3 && (
            <RunStep
              name={name}
              onNameChange={setName}
              selectedSearch={selectedSearch}
              selectedRecordType={selectedRecordType}
              positiveCount={positiveControls.length}
              negativeCount={negativeControls.length}
              enableCV={enableCV}
              onEnableCVChange={setEnableCV}
              kFolds={kFolds}
              kFoldsDraft={kFoldsDraft}
              onKFoldsChange={setKFolds}
              onKFoldsDraftChange={setKFoldsDraft}
              enrichments={enrichments}
              onToggleEnrichment={toggleEnrichment}
              optimizeSpecs={optimizeSpecs}
              optimizationBudget={optimizationBudget}
              optimizationBudgetDraft={optimizationBudgetDraft}
              onBudgetChange={setOptimizationBudget}
              onBudgetDraftChange={setOptimizationBudgetDraft}
              optimizationObjective={optimizationObjective}
              onObjectiveChange={setOptimizationObjective}
              batchMode={batchMode}
              onBatchModeChange={setBatchMode}
              batchOrganisms={batchOrganisms}
              onBatchOrganismsChange={setBatchOrganisms}
              organismOptions={organismOptions}
              organismParamName={organismParamName}
              batchOrganismControls={batchOrganismControls}
              onBatchOrganismControlsChange={setBatchOrganismControls}
            />
          )}
        </div>

        {attemptedSteps.has(step) && stepValidation.message && (
          <div className="mt-3 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            {stepValidation.message}
          </div>
        )}

        {storeError && (
          <div className="mt-3 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            <span className="font-semibold">Experiment failed:</span> {storeError}
          </div>
        )}

        <div className="mt-4 flex items-center justify-between border-t border-border pt-4">
          <Button variant="ghost" size="sm" onClick={goBack}>
            <ArrowLeft className="h-3.5 w-3.5" />
            {step === 0 ? "Back to list" : "Back"}
          </Button>
          {step < STEPS.length - 1 ? (
            <Button onClick={goNext} disabled={!canNext()}>
              Next
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          ) : (
            <Button
              onClick={runOrValidate}
              disabled={!canNext() || isRunning}
              loading={isRunning}
            >
              {!isRunning && <FlaskConical className="h-3.5 w-3.5" />}
              {isRunning ? "Running..." : "Run Experiment"}
            </Button>
          )}
        </div>
      </div>

      <div className="w-96 shrink-0">
        <AiAssistantPanel
          siteId={siteId}
          step={currentAiStep}
          context={aiContext}
          onSuggestionApply={handleSuggestionApply}
          onGeneAdd={handleGeneAdd}
          onParamsApply={handleParamsApply}
          onRunConfigApply={handleRunConfigApply}
        />
      </div>
    </div>
  );
}
