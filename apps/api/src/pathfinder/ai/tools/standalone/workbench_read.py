"""Read-only workbench experiment tools.

Each tool reads the experiment that the chat is associated with. A chat without
an experiment gets an error result, not empty data.
"""

from pydantic_ai import RunContext

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._workbench_models import (
    ClassificationCounts,
    ConfidenceScoresResult,
    EnrichmentResultsResponse,
    EnsembleAnalysisResult,
    EvaluationSummaryResult,
    ExperimentConfigResult,
    GeneListResult,
    SampleGeneIds,
    StepContributionsResult,
    WorkbenchError,
)
from pathfinder.services.experiment.store import get_experiment_store
from pathfinder.services.experiment.types import Experiment


async def _get_experiment(ctx: RunContext[AgentDeps]) -> Experiment | None:
    experiment_id = ctx.deps.experiment_id
    if not experiment_id:
        return None
    store = get_experiment_store()
    return await store.aget(experiment_id)


async def get_evaluation_summary(
    ctx: RunContext[AgentDeps],
) -> EvaluationSummaryResult | WorkbenchError:
    """Classification metrics, confusion counts, and sample gene IDs."""
    exp = await _get_experiment(ctx)
    if not exp:
        return WorkbenchError(error="Conversation has no associated experiment")
    if not exp.metrics:
        return WorkbenchError(error="Experiment has no evaluation metrics yet")

    return EvaluationSummaryResult(
        metrics=exp.metrics,
        classification_counts=ClassificationCounts(
            true_positives=len(exp.true_positive_genes),
            false_positives=len(exp.false_positive_genes),
            false_negatives=len(exp.false_negative_genes),
            true_negatives=len(exp.true_negative_genes),
        ),
        sample_gene_ids=SampleGeneIds(
            true_positives=[g.id for g in exp.true_positive_genes[:5]],
            false_positives=[g.id for g in exp.false_positive_genes[:5]],
            false_negatives=[g.id for g in exp.false_negative_genes[:5]],
            true_negatives=[g.id for g in exp.true_negative_genes[:5]],
        ),
        status=exp.status,
    )


async def get_enrichment_results(
    ctx: RunContext[AgentDeps],
) -> EnrichmentResultsResponse | WorkbenchError:
    """GO term, pathway, and word enrichment for the current experiment."""
    exp = await _get_experiment(ctx)
    if not exp:
        return WorkbenchError(error="Conversation has no associated experiment")
    if not exp.enrichment_results:
        return WorkbenchError(
            error="No enrichment results available for this experiment"
        )

    return EnrichmentResultsResponse(
        enrichment_results=exp.enrichment_results,
        count=len(exp.enrichment_results),
    )


async def get_confidence_scores(
    ctx: RunContext[AgentDeps],
) -> ConfidenceScoresResult | WorkbenchError:
    """Cross-validation confidence scores for the current experiment."""
    exp = await _get_experiment(ctx)
    if not exp:
        return WorkbenchError(error="Conversation has no associated experiment")
    if not exp.cross_validation:
        return WorkbenchError(
            error="No cross-validation results available for this experiment"
        )

    return ConfidenceScoresResult(cross_validation=exp.cross_validation)


async def get_step_contributions(
    ctx: RunContext[AgentDeps],
) -> StepContributionsResult | WorkbenchError:
    """Per-step recall/FPR deltas and verdict for the current experiment."""
    exp = await _get_experiment(ctx)
    if not exp:
        return WorkbenchError(error="Conversation has no associated experiment")
    if not exp.step_analysis:
        return WorkbenchError(error="No step analysis available for this experiment")

    return StepContributionsResult(
        step_contributions=exp.step_analysis.step_contributions,
        count=len(exp.step_analysis.step_contributions),
    )


async def get_experiment_config(
    ctx: RunContext[AgentDeps],
) -> ExperimentConfigResult | WorkbenchError:
    """Experiment configuration, status, and WDK strategy/step IDs."""
    exp = await _get_experiment(ctx)
    if not exp:
        return WorkbenchError(error="Conversation has no associated experiment")

    return ExperimentConfigResult(
        config=exp.config,
        status=exp.status,
        wdk_strategy_id=exp.wdk_strategy_id,
        wdk_step_id=exp.wdk_step_id,
        notes=exp.notes,
        created_at=exp.created_at,
        completed_at=exp.completed_at,
    )


async def get_ensemble_analysis(
    ctx: RunContext[AgentDeps],
) -> EnsembleAnalysisResult | WorkbenchError:
    """Full ensemble step analysis for the current experiment."""
    exp = await _get_experiment(ctx)
    if not exp:
        return WorkbenchError(error="Conversation has no associated experiment")
    if not exp.step_analysis:
        return WorkbenchError(error="No step analysis available for this experiment")

    return EnsembleAnalysisResult(step_analysis=exp.step_analysis)


async def get_result_gene_lists(
    ctx: RunContext[AgentDeps],
    classification: str,
    limit: int = 50,
) -> GeneListResult | WorkbenchError:
    """Gene IDs for a classification category (tp/fp/fn/tn).

    Args:
        classification: Classification category: 'tp', 'fp', 'fn', or 'tn'.
        limit: Maximum number of gene IDs to return (max 200).
    """
    valid: set[str] = {"tp", "fp", "fn", "tn"}
    if classification not in valid:
        return WorkbenchError(
            error=f"Invalid classification '{classification}'. "
            f"Must be one of: {', '.join(sorted(valid))}"
        )

    exp = await _get_experiment(ctx)
    if not exp:
        return WorkbenchError(error="Conversation has no associated experiment")

    gene_list = {
        "tp": exp.true_positive_genes,
        "fp": exp.false_positive_genes,
        "fn": exp.false_negative_genes,
        "tn": exp.true_negative_genes,
    }[classification]

    capped = min(limit, 200)
    selected = gene_list[:capped]

    return GeneListResult(
        classification=classification,
        genes=selected,
        returned=len(selected),
        total=len(gene_list),
    )
