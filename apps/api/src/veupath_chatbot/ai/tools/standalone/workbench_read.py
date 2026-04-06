"""Standalone read-only workbench experiment tools for pydantic-ai agents.

Provides:
- ``get_evaluation_summary`` -- classification metrics and sample gene IDs
- ``get_enrichment_results`` -- GO/pathway/word enrichment results
- ``get_confidence_scores`` -- cross-validation confidence scores
- ``get_step_contributions`` -- step contribution (ablation) analysis
- ``get_experiment_config`` -- experiment configuration and status
- ``get_ensemble_analysis`` -- full ensemble step analysis
- ``get_result_gene_lists`` -- gene IDs for a classification category
"""

from pydantic_ai import RunContext

from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.ai.tools.standalone._workbench_models import (
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
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import Experiment


async def _get_experiment(ctx: RunContext[AgentDeps]) -> Experiment | None:
    """Fetch the current experiment from the store."""
    experiment_id = ctx.deps.experiment_id
    if not experiment_id:
        return None
    store = get_experiment_store()
    return await store.aget(experiment_id)


async def get_evaluation_summary(
    ctx: RunContext[AgentDeps],
) -> EvaluationSummaryResult | WorkbenchError:
    """Get a summary of the experiment evaluation results.

    Returns classification metrics, confusion matrix counts, and sample
    gene IDs from each classification category (TP/FP/FN/TN).
    """
    exp = await _get_experiment(ctx)
    if not exp:
        return WorkbenchError(error="Experiment not found")
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
    """Get the enrichment analysis results for this experiment.

    Returns GO term, pathway, and word enrichment results. Each result
    includes the analysis type, enriched terms with p-values, and
    background statistics.
    """
    exp = await _get_experiment(ctx)
    if not exp:
        return WorkbenchError(error="Experiment not found")
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
    """Get cross-validation confidence scores for this experiment.

    Returns mean metrics, per-fold metrics, standard deviations, and
    overfitting assessment. Indicates how robustly the strategy generalises.
    """
    exp = await _get_experiment(ctx)
    if not exp:
        return WorkbenchError(error="Experiment not found")
    if not exp.cross_validation:
        return WorkbenchError(
            error="No cross-validation results available for this experiment"
        )

    return ConfidenceScoresResult(
        cross_validation=exp.cross_validation,
    )


async def get_step_contributions(
    ctx: RunContext[AgentDeps],
) -> StepContributionsResult | WorkbenchError:
    """Get the step contribution (ablation) analysis for this experiment.

    Returns per-step recall delta, FPR delta, and verdict indicating whether
    each search step adds meaningful value to the strategy.
    """
    exp = await _get_experiment(ctx)
    if not exp:
        return WorkbenchError(error="Experiment not found")
    if not exp.step_analysis:
        return WorkbenchError(
            error="No step analysis available for this experiment"
        )

    return StepContributionsResult(
        step_contributions=exp.step_analysis.step_contributions,
        count=len(exp.step_analysis.step_contributions),
    )


async def get_experiment_config(
    ctx: RunContext[AgentDeps],
) -> ExperimentConfigResult | WorkbenchError:
    """Get the experiment configuration, status, and WDK strategy IDs.

    Returns the full config (search name, parameters, controls, mode),
    current execution status, and WDK strategy/step IDs if available.
    """
    exp = await _get_experiment(ctx)
    if not exp:
        return WorkbenchError(error="Experiment not found")

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
    """Get the full ensemble step analysis for this experiment.

    Returns step evaluations, operator comparisons, step contributions,
    and parameter sensitivities. Useful for understanding multi-step
    strategy behaviour in detail.
    """
    exp = await _get_experiment(ctx)
    if not exp:
        return WorkbenchError(error="Experiment not found")
    if not exp.step_analysis:
        return WorkbenchError(
            error="No step analysis available for this experiment"
        )

    return EnsembleAnalysisResult(
        step_analysis=exp.step_analysis,
    )


async def get_result_gene_lists(
    ctx: RunContext[AgentDeps],
    classification: str,
    limit: int = 50,
) -> GeneListResult | WorkbenchError:
    """Get gene IDs for a specific classification category.

    Returns gene IDs and basic metadata (name, organism, product) for
    the requested category. Use 'tp' for hits that are known positives,
    'fp' for hits that are known negatives, 'fn' for missed known positives,
    'tn' for non-hits that are known negatives.

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
        return WorkbenchError(error="Experiment not found")

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
