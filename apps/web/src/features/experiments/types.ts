import type {
  StepEvaluation,
  OperatorComparison,
  StepContribution,
  ParameterSensitivity,
} from "@pathfinder/shared";

export interface TrialHistoryEntry {
  trialNumber: number;
  score: number;
  bestScore: number;
}

export interface StepAnalysisLiveItems {
  evaluations: StepEvaluation[];
  operators: OperatorComparison[];
  contributions: StepContribution[];
  sensitivities: ParameterSensitivity[];
}
