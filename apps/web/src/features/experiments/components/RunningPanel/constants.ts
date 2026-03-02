import { CombineOperator } from "@pathfinder/shared";

export const PHASE_LABELS: Record<string, string> = {
  started: "Initializing",
  optimizing: "Optimizing parameters",
  evaluating: "Evaluating",
  step_analysis: "Analyzing strategy",
  cross_validating: "Cross-validating",
  enriching: "Computing enrichment",
  completed: "Complete",
  error: "Error",
};

export const STEP_ANALYSIS_PHASE_LABELS: Record<string, string> = {
  step_evaluation: "Per-Step Evaluation",
  operator_comparison: "Operator Comparison",
  contribution: "Step Contribution (Ablation)",
  sensitivity: "Parameter Sensitivity",
};

export const NODE_W = 120;
export const NODE_H = 32;
export const COL_GAP = 44;
export const ROW_GAP = 10;

export const NODE_STYLES: Record<
  string,
  { fill: string; stroke: string; textFill: string }
> = {
  search: { fill: "#ecfdf5", stroke: "#6ee7b7", textFill: "#065f46" },
  combine: { fill: "#eff6ff", stroke: "#93c5fd", textFill: "#1e40af" },
  transform: { fill: "#f5f3ff", stroke: "#c4b5fd", textFill: "#5b21b6" },
};

export const MUTATED_STROKE = "hsl(var(--chart-3))";

export const OP_FILL: Record<string, string> = {
  [CombineOperator.INTERSECT]: "#dbeafe",
  [CombineOperator.UNION]: "#dcfce7",
  [CombineOperator.MINUS]: "#ffedd5",
  [CombineOperator.LONLY]: "#ffedd5",
  [CombineOperator.RMINUS]: "#fee2e2",
  [CombineOperator.RONLY]: "#fee2e2",
  [CombineOperator.COLOCATE]: "#e9d5ff",
};

export const OP_TEXT: Record<string, string> = {
  [CombineOperator.INTERSECT]: "#1d4ed8",
  [CombineOperator.UNION]: "#15803d",
  [CombineOperator.MINUS]: "#c2410c",
  [CombineOperator.LONLY]: "#c2410c",
  [CombineOperator.RMINUS]: "#b91c1c",
  [CombineOperator.RONLY]: "#b91c1c",
  [CombineOperator.COLOCATE]: "#7c3aed",
};

export const VERDICT_STYLE: Record<string, { bg: string; text: string }> = {
  essential: {
    bg: "bg-green-100 dark:bg-green-900/30",
    text: "text-green-700 dark:text-green-400",
  },
  helpful: {
    bg: "bg-blue-100 dark:bg-blue-900/30",
    text: "text-blue-700 dark:text-blue-400",
  },
  neutral: {
    bg: "bg-gray-100 dark:bg-gray-800/40",
    text: "text-gray-600 dark:text-gray-400",
  },
  harmful: {
    bg: "bg-red-100 dark:bg-red-900/30",
    text: "text-red-700 dark:text-red-400",
  },
};
