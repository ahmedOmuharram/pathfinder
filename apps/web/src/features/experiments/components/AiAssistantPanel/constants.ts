import type { WizardStep } from "../../api";

export type QuickAction = { label: string; prompt: string };

export const STEP_LABELS: Record<WizardStep, string> = {
  search: "Search Selection",
  parameters: "Parameter Configuration",
  controls: "Control Gene Selection",
  run: "Run Configuration",
  results: "Results Interpretation",
  analysis: "Deep Results Analysis",
};

export const STEP_PLACEHOLDERS: Record<WizardStep, string> = {
  search: "e.g. Find genes involved in invasion in P. falciparum",
  parameters: "e.g. Which organism filter applies to this search?",
  controls: "e.g. Known positive control genes for this analysis type?",
  run: "e.g. Should cross-validation be enabled given these control sizes?",
  results: "e.g. How should these metrics inform my research question?",
  analysis:
    "Ask about specific genes, patterns in results, why certain genes are false positives...",
};

export const QUICK_ACTION_PROMPTS: Partial<
  Record<WizardStep, QuickAction | QuickAction[]>
> = {
  search: {
    label: "Search recommendations",
    prompt:
      "Based on the site and record type context, suggest the most relevant VEuPathDB searches for my research. Pick the ones most useful for experiment benchmarking with control genes.",
  },
  parameters: {
    label: "Parameter guidance",
    prompt:
      "Suggest optimal parameter values for this search based on best practices and the biological context. Output them as structured suggestions I can apply.",
  },
  controls: {
    label: "Control gene candidates",
    prompt:
      "Suggest positive and negative control genes for this search. Look up published controls in literature and verify the gene IDs exist on this site.",
  },
  run: {
    label: "Run configuration",
    prompt:
      "Recommend the best run configuration for this experiment: name, whether to enable robustness analysis, fold count, and which enrichment analyses to run.",
  },
  analysis: [
    {
      label: "Explain false positives",
      prompt:
        "Why are some negative control genes showing up in the results? Analyze the false positives.",
    },
    {
      label: "Find patterns",
      prompt: "What common attributes or features do the top results share?",
    },
    {
      label: "Compare TP vs FP",
      prompt:
        "Compare the true positive genes against the false positive genes. What distinguishes them?",
    },
    {
      label: "Summarize results",
      prompt:
        "Give me a comprehensive summary of these experiment results and actionable next steps.",
    },
  ],
};
