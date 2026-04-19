"""Experiment execution orchestrator.

Coordinates the full experiment lifecycle: evaluation, metrics computation,
optional cross-validation, and optional enrichment analysis.

Each phase is a function in a dedicated submodule under ``phases/``.  The
public ``run_experiment()`` function orchestrates phase sequencing,
lifecycle management, and error handling.
"""

import time
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject
from pathfinder.services.experiment.helpers import ProgressCallback
from pathfinder.services.experiment.service.context import (
    PhaseContext,
    get_experiment_lock,
)
from pathfinder.services.experiment.service.phases.evaluate import (
    phase_evaluate,
    phase_persist_strategy,
    phase_rank_metrics,
    phase_step_analysis,
)
from pathfinder.services.experiment.service.phases.optimize import (
    phase_optimize_parameters,
    phase_optimize_tree_knobs,
)
from pathfinder.services.experiment.service.phases.validate import (
    phase_cross_validate,
    phase_enrich,
    phase_robustness,
)
from pathfinder.services.experiment.store import get_experiment_store
from pathfinder.services.experiment.types import (
    Experiment,
    ExperimentConfig,
    ExperimentProgressPhase,
)

logger = get_logger(__name__)


async def run_experiment(
    config: ExperimentConfig,
    *,
    user_id: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> Experiment:
    """Execute a full experiment and persist the result.

    :param config: Experiment configuration.
    :param user_id: Owning user ID (for IDOR protection).
    :param progress_callback: Optional async callback for SSE progress events.
    :returns: Completed experiment with all results.
    """
    experiment_id = f"exp_{uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()
    store = get_experiment_store()

    experiment = Experiment(
        id=experiment_id,
        config=config,
        user_id=user_id,
        status="running",
        created_at=now,
    )
    store.save(experiment)

    start = time.monotonic()

    async def _emit(phase: ExperimentProgressPhase, **extra: object) -> None:
        if progress_callback:
            event: JSONObject = {
                "type": "experiment_progress",
                "data": {
                    "experimentId": experiment_id,
                    "phase": phase,
                    **cast("JSONObject", dict(extra)),
                },
            }
            await progress_callback(event)

    experiment_lock = get_experiment_lock(experiment_id)
    await experiment_lock.acquire()
    try:
        await _emit("started", message="Starting evaluation...")

        pctx = PhaseContext(
            config=config,
            experiment=experiment,
            emit=_emit,
            store=store,
        )

        # Phase 1: Control-test evaluation + metrics + gene enrichment
        result, metrics = await phase_evaluate(pctx)

        plan_tree: StrategyStepNode | None = (
            config.step_tree if config.is_tree_mode else None
        )

        # Phase 2: Step analysis (multi-step only)
        if (
            config.is_tree_mode
            and plan_tree is not None
            and config.enable_step_analysis
        ):
            await phase_step_analysis(pctx, plan_tree, result)

        # Phase 3: Persist WDK strategy for result exploration
        await phase_persist_strategy(pctx, plan_tree)

        # Phase 4: Rank-based metrics
        is_ranked = config.sort_attribute is not None
        ordered_ids = await phase_rank_metrics(pctx)

        # Phase 5: Robustness / bootstrap CIs
        await phase_robustness(pctx, ordered_ids, is_ranked=is_ranked)

        # Phase 6: Parameter optimization (single-step only)
        if (
            not config.is_tree_mode
            and config.optimization_specs
            and len(config.optimization_specs) > 0
        ):
            _, metrics = await phase_optimize_parameters(pctx, metrics)

        # Phase 7: Tree-knob optimization (multi-step only)
        has_tree_knobs = bool(config.threshold_knobs or config.operator_knobs)
        if config.is_tree_mode and has_tree_knobs and plan_tree is not None:
            await phase_optimize_tree_knobs(pctx, plan_tree)

        # Phase 8: Cross-validation
        if (
            config.enable_cross_validation
            and config.positive_controls
            and config.negative_controls
        ):
            await phase_cross_validate(pctx, plan_tree)

        # Phase 9: Enrichment analysis
        if config.enrichment_types:
            await phase_enrich(pctx)

        # Finalize
        experiment.status = "completed"
        experiment.total_time_seconds = time.monotonic() - start
        experiment.completed_at = datetime.now(UTC).isoformat()
        store.save(experiment)

        await _emit("completed", message="Experiment complete")

    except Exception as exc:
        experiment.status = "error"
        experiment.error = str(exc)
        experiment.total_time_seconds = time.monotonic() - start
        store.save(experiment)
        await _emit("error", error=str(exc))
        raise
    else:
        return experiment
    finally:
        experiment_lock.release()
