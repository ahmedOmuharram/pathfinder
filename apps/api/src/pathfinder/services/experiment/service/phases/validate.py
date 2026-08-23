"""Validation and enrichment phases: robustness (bootstrap CIs),
cross-validation, and enrichment analysis.

These phases run late in the experiment lifecycle to assess result
reliability and add biological context.
"""

from assistant_core.platform.logging import get_logger

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.platform.errors import AppError
from pathfinder.services.enrichment.parser import upsert_enrichment_result
from pathfinder.services.enrichment.service import EnrichmentService
from pathfinder.services.experiment.cross_validation import (
    CrossValidationOptions,
    run_cross_validation,
)
from pathfinder.services.experiment.helpers import ControlsContext
from pathfinder.services.experiment.rank_metrics import fetch_ordered_result_ids
from pathfinder.services.experiment.robustness import (
    BootstrapOptions,
    compute_robustness,
)
from pathfinder.services.experiment.service.context import PhaseContext
from pathfinder.services.experiment.types import ExperimentConfig
from pathfinder.services.gene_sets.wdk_helpers import (
    build_enrichment_params_from_gene_ids,
)

logger = get_logger(__name__)


async def phase_robustness(
    pctx: PhaseContext,
    ordered_ids: list[str],
    *,
    is_ranked: bool,
) -> None:
    """Compute bootstrap confidence intervals."""
    config, experiment = pctx.config, pctx.experiment
    if experiment.wdk_step_id is None:
        return

    try:
        await pctx.emit("evaluating", message="Computing robustness estimates...")

        if not ordered_ids:
            ordered_ids = await fetch_ordered_result_ids(
                site_id=config.site_id,
                step_id=experiment.wdk_step_id,
            )

        if ordered_ids:
            experiment.robustness = compute_robustness(
                result_ids=ordered_ids,
                positive_ids=config.positive_controls or [],
                negative_ids=config.negative_controls or [],
                options=BootstrapOptions(
                    n_bootstrap=200, include_rank_metrics=is_ranked
                ),
            )
            pctx.store.save(experiment)
    except (AppError, ZeroDivisionError) as exc:
        logger.warning(
            "Robustness computation failed",
            experiment_id=experiment.id,
            error=str(exc),
        )


async def phase_cross_validate(
    pctx: PhaseContext,
    final_tree: StrategyStepNode | None,
) -> None:
    """Run k-fold cross-validation (tree or single-step)."""
    config, experiment = pctx.config, pctx.experiment
    await pctx.emit(
        "cross_validating",
        message=f"Running {config.k_folds}-fold cross-validation...",
    )

    async def _cv_progress(fold_idx: int, total: int) -> None:
        await pctx.emit(
            "cross_validating",
            message=f"Fold {fold_idx + 1} of {total}",
            cvFoldIndex=fold_idx,
            cvTotalFolds=total,
        )

    ctx = ControlsContext.from_config(config)
    experiment.cross_validation = await run_cross_validation(
        ctx,
        final_tree,
        config.search_name if final_tree is None else None,
        config.parameters if final_tree is None else None,
        CrossValidationOptions(
            k=config.k_folds,
            full_metrics=experiment.metrics,
            progress_callback=_cv_progress,
        ),
    )
    pctx.store.save(experiment)


async def _build_enrichment_context(
    config: ExperimentConfig,
) -> tuple[str, dict[str, ParamValue], str]:
    """Resolve search_name, parameters, and record_type for enrichment.

    Gene-ID experiments may lack a WDK step and search_name. In that case
    build a temporary GeneByLocusTag dataset so enrichment can proceed.
    """
    search_name = config.search_name
    parameters = config.parameters
    record_type = config.record_type

    if not search_name and config.target_gene_ids:
        (
            search_name,
            parameters,
            record_type,
        ) = await build_enrichment_params_from_gene_ids(
            config.site_id, config.target_gene_ids
        )

    return search_name, parameters, record_type


async def phase_enrich(
    pctx: PhaseContext,
) -> None:
    """Run enrichment analyses on experiment results."""
    config, experiment = pctx.config, pctx.experiment

    await pctx.emit("enriching", message="Running enrichment analyses...")

    step_id = experiment.wdk_step_id
    search_name, parameters, record_type = await _build_enrichment_context(config)

    svc = EnrichmentService()
    enrich_results, _ = await svc.run_batch(
        site_id=config.site_id,
        analysis_types=config.enrichment_types,
        step_id=step_id,
        search_name=search_name,
        record_type=record_type,
        parameters=parameters,
    )
    for enrich_result in enrich_results:
        upsert_enrichment_result(experiment.enrichment_results, enrich_result)
    pctx.store.save(experiment)
