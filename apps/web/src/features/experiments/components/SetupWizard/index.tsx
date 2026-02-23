import { ArrowLeft, ArrowRight, Check, FlaskConical, Loader2 } from "lucide-react";
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
    toggleEnrichment,
    goBack,
    goNext,
    runOrValidate,
    canNext,
  } = wizard;

  return (
    <div className="flex h-full">
      <div className="flex flex-1 flex-col p-6">
        <div className="mb-6 flex items-center gap-2">
          {STEPS.map((label, i) => (
            <div key={label} className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => i <= step && setStep(i)}
                className={`flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-semibold transition ${
                  i < step
                    ? "bg-emerald-100 text-emerald-700"
                    : i === step
                      ? "bg-slate-900 text-white"
                      : "bg-slate-100 text-slate-400"
                }`}
              >
                {i < step ? <Check className="h-3.5 w-3.5" /> : i + 1}
              </button>
              <span
                className={`text-[11px] font-medium ${i === step ? "text-slate-800" : "text-slate-400"}`}
              >
                {label}
              </span>
              {i < STEPS.length - 1 && <div className="mx-1 h-px w-8 bg-slate-200" />}
            </div>
          ))}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
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
              optimizeSpecs={{}}
              onOptimizeSpecChange={() => {}}
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
              selectedSearch={selectedSearch}
              selectedRecordType={selectedRecordType}
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
            />
          )}
        </div>

        {attemptedSteps.has(step) && stepValidation.message && (
          <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[11px] text-red-700">
            {stepValidation.message}
          </div>
        )}

        {storeError && (
          <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[11px] text-red-700">
            <span className="font-semibold">Experiment failed:</span> {storeError}
          </div>
        )}

        <div className="mt-4 flex items-center justify-between border-t border-slate-200 pt-4">
          <button
            type="button"
            onClick={goBack}
            className="flex items-center gap-1 text-[12px] font-medium text-slate-600 transition hover:text-slate-800"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            {step === 0 ? "Back to list" : "Back"}
          </button>
          {step < STEPS.length - 1 ? (
            <button
              type="button"
              onClick={goNext}
              className={`flex items-center gap-1 rounded-md px-4 py-2 text-[12px] font-medium transition ${
                canNext()
                  ? "bg-slate-900 text-white hover:bg-slate-800"
                  : "bg-slate-900/60 text-white/80 cursor-not-allowed"
              }`}
            >
              Next
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          ) : (
            <button
              type="button"
              onClick={runOrValidate}
              className={`flex items-center gap-2 rounded-md px-4 py-2 text-[12px] font-semibold transition ${
                canNext() && !isRunning
                  ? "bg-indigo-600 text-white hover:bg-indigo-700"
                  : "bg-indigo-600/60 text-white/80 cursor-not-allowed"
              }`}
            >
              {isRunning ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <FlaskConical className="h-3.5 w-3.5" />
                  Run Experiment
                </>
              )}
            </button>
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
