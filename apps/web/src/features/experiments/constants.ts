import type { EnrichmentAnalysisType } from "@pathfinder/shared";

export type SortDir = "asc" | "desc";
export type WdkSortDir = "ASC" | "DESC";

export const ENRICHMENT_ANALYSIS_LABELS: Record<EnrichmentAnalysisType, string> = {
  go_function: "GO: Molecular Function",
  go_component: "GO: Cellular Component",
  go_process: "GO: Biological Process",
  pathway: "Metabolic Pathway",
  word: "Word Enrichment",
};

export const OBJECTIVE_OPTIONS: {
  value: string;
  label: string;
  description: string;
}[] = [
  {
    value: "balanced_accuracy",
    label: "Balanced Accuracy",
    description: "(TPR + TNR) / 2",
  },
  {
    value: "f1",
    label: "F1 Score",
    description: "Harmonic mean of precision & recall",
  },
  {
    value: "recall",
    label: "Recall (Sensitivity)",
    description: "TP / (TP + FN)",
  },
  { value: "precision", label: "Precision", description: "TP / (TP + FP)" },
  { value: "specificity", label: "Specificity", description: "TN / (TN + FP)" },
  {
    value: "mcc",
    label: "MCC",
    description: "Matthews Correlation Coefficient",
  },
  {
    value: "youdens_j",
    label: "Youden's J",
    description: "Sensitivity + Specificity - 1",
  },
  { value: "f_beta", label: "F-beta", description: "Weighted F-measure" },
];
