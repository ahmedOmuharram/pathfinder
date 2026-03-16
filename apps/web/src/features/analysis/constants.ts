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
