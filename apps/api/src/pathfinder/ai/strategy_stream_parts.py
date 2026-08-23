"""Stream parts of the strategy product: graph, strategy, gene sets, experiments."""

from assistant_core.conversation.stream_parts.registry import (
    StreamPartRegistry,
)
from shared_py.stream_parts.enrichment import EnrichmentResultsChunk
from shared_py.stream_parts.gene_set import GeneSet
from shared_py.stream_parts.graph import GraphCleared, GraphPlan, GraphSnapshot
from shared_py.stream_parts.optimization import OptimizationSnapshot
from shared_py.stream_parts.phase import PhaseChange
from shared_py.stream_parts.strategy import StrategyLink, StrategyMeta, StrategyPatch

from pathfinder.ai.graph.stream_events import StrategyRevisionPayload
from pathfinder.services.experiment.scored_comparison import ScoredComparison
from pathfinder.services.experiment.variant_comparison import VariantComparison


def register_strategy_stream_parts(registry: StreamPartRegistry) -> None:
    registry.register("data-graph-snapshot", GraphSnapshot)
    registry.register("data-graph-cleared", GraphCleared)
    registry.register("data-strategy-meta", StrategyMeta)
    registry.register("data-strategy-link", StrategyLink)
    registry.register("data-strategy-revision", StrategyRevisionPayload)
    registry.register("data-gene-set", GeneSet)
    registry.register("data-enrichment-results", EnrichmentResultsChunk)
    registry.register("data-variant-comparison", VariantComparison)
    registry.register("data-scored-comparison", ScoredComparison)
    registry.register_schema_only("graph_plan", GraphPlan)
    registry.register_schema_only("strategy_patch", StrategyPatch)
    registry.register_schema_only("optimization_snapshot", OptimizationSnapshot)
    registry.register_schema_only("phase_change", PhaseChange)
