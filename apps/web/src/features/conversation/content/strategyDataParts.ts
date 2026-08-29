import { DataEnrichmentResults } from "./parts/DataEnrichmentResults";
import { DataGeneSet } from "./parts/DataGeneSet";
import { DataGraphCleared } from "./parts/DataGraphCleared";
import { DataGraphSnapshot } from "./parts/DataGraphSnapshot";
import { DataScoredComparison } from "./parts/DataScoredComparison";
import { DataStrategyLink } from "./parts/DataStrategyLink";
import { DataStrategyMeta } from "./parts/DataStrategyMeta";
import { DataVariantComparison } from "./parts/DataVariantComparison";
import { DataVerificationSummary } from "./parts/DataVerificationSummary";
import type { DataPartComponentMap } from "./dataPartComponentMap";

/** Parts of the strategy product: graph, strategy, gene sets, experiments. */
export type StrategyDataPartKind =
  | "data-ledger-update"
  | "data-enrichment-results"
  | "data-strategy-link"
  | "data-strategy-meta"
  | "data-graph-snapshot"
  | "data-graph-cleared"
  | "data-variant-comparison"
  | "data-scored-comparison"
  | "data-gene-set"
  | "data-verification-summary";

export const strategyDataPartComponents: DataPartComponentMap<StrategyDataPartKind> = {
  "data-ledger-update": () => null,
  "data-enrichment-results": DataEnrichmentResults,
  "data-strategy-link": DataStrategyLink,
  "data-strategy-meta": DataStrategyMeta,
  "data-graph-snapshot": DataGraphSnapshot,
  "data-graph-cleared": DataGraphCleared,
  "data-variant-comparison": DataVariantComparison,
  "data-scored-comparison": DataScoredComparison,
  "data-gene-set": DataGeneSet,
  "data-verification-summary": DataVerificationSummary,
};
