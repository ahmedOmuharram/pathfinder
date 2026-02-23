import type { WizardStep } from "../../api";

export const STEP_LABELS: Record<WizardStep, string> = {
  search: "Search Selection",
  parameters: "Parameter Configuration",
  controls: "Control Gene Selection",
  run: "Run Configuration",
  results: "Results Interpretation",
};

export const STEP_PLACEHOLDERS: Record<WizardStep, string> = {
  search: "e.g. I want to find genes involved in invasion in P. falciparum...",
  parameters: "e.g. What organism should I filter by for my search?",
  controls: "e.g. What are known positive control genes for this type of analysis?",
  run: "e.g. Should I enable cross-validation with these control sizes?",
  results: "e.g. What do these metrics mean for my research question?",
};

export const QUICK_ACTION_PROMPTS: Partial<
  Record<WizardStep, { label: string; prompt: string }>
> = {
  search: {
    label: "Suggest searches",
    prompt:
      "Based on the site and record type context, suggest the most relevant VEuPathDB searches for my research. Pick the ones most useful for experiment benchmarking with control genes.",
  },
  parameters: {
    label: "Suggest parameter values",
    prompt:
      "Suggest optimal parameter values for this search based on best practices and the biological context. Output them as structured suggestions I can apply.",
  },
  controls: {
    label: "Suggest control genes",
    prompt:
      "Suggest positive and negative control genes for this search. Look up published controls in literature and verify the gene IDs exist on this site.",
  },
  run: {
    label: "Recommend run settings",
    prompt:
      "Recommend the best run configuration for this experiment — name, whether to enable robustness analysis, fold count, and which enrichment analyses to run.",
  },
};
