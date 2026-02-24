import type { WizardStep } from "../../api";

export const STEP_LABELS: Record<WizardStep, string> = {
  search: "Search Selection",
  parameters: "Parameter Configuration",
  controls: "Control Gene Selection",
  run: "Run Configuration",
  results: "Results Interpretation",
};

export const STEP_PLACEHOLDERS: Record<WizardStep, string> = {
  search: "e.g. Find genes involved in invasion in P. falciparum",
  parameters: "e.g. Which organism filter applies to this search?",
  controls: "e.g. Known positive control genes for this analysis type?",
  run: "e.g. Should cross-validation be enabled given these control sizes?",
  results: "e.g. How should these metrics inform my research question?",
};

export const QUICK_ACTION_PROMPTS: Partial<
  Record<WizardStep, { label: string; prompt: string }>
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
};
