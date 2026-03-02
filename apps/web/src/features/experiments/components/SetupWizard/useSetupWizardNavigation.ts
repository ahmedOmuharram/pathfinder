import { useCallback, useState } from "react";
import { useExperimentViewStore } from "../../store";
import type { WizardStep as AiWizardStep } from "../../api";

const AI_STEP_MAP: AiWizardStep[] = ["search", "parameters", "controls", "run"];

export function useSetupWizardNavigation() {
  const { setView } = useExperimentViewStore();

  const [step, setStep] = useState(0);
  const [attemptedSteps, setAttemptedSteps] = useState<Set<number>>(new Set());

  const currentAiStep = AI_STEP_MAP[step];

  const goBack = useCallback(() => {
    if (step === 0) setView("mode-select");
    else setStep((s) => s - 1);
  }, [step, setView]);

  const markStepAttempted = useCallback(() => {
    setAttemptedSteps((prev) => new Set(prev).add(step));
  }, [step]);

  const advanceStep = useCallback(() => {
    setStep((s) => s + 1);
  }, []);

  return {
    step,
    setStep,
    attemptedSteps,
    currentAiStep,
    goBack,
    markStepAttempted,
    advanceStep,
  };
}
