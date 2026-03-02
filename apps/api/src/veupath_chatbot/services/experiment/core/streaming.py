"""SSE event generators for experiment execution."""

from __future__ import annotations

import asyncio
import copy
from collections.abc import AsyncIterator, Awaitable, Callable

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.service import run_experiment
from veupath_chatbot.services.experiment.types import (
    BatchExperimentConfig,
    Experiment,
    ExperimentConfig,
    experiment_to_json,
)
from veupath_chatbot.transport.http.sse import sse_stream

logger = get_logger(__name__)


def experiment_sse_generator(
    config: ExperimentConfig,
) -> AsyncIterator[str]:
    """SSE event stream for a single experiment execution."""

    async def _producer(send: Callable[[JSONObject], Awaitable[None]]) -> None:
        try:
            result = await run_experiment(config, progress_callback=send)
            await send(
                {
                    "type": "experiment_complete",
                    "data": experiment_to_json(result),
                }
            )
        except Exception as exc:
            logger.error("Experiment failed", error=str(exc), exc_info=True)
            await send(
                {
                    "type": "experiment_error",
                    "data": {"error": str(exc)},
                }
            )
        finally:
            await send({"type": "experiment_end", "data": {}})

    return sse_stream(_producer, {"experiment_end"})


def batch_sse_generator(
    batch_config: BatchExperimentConfig,
) -> AsyncIterator[str]:
    """SSE event stream for cross-organism batch experiments."""
    from veupath_chatbot.services.experiment.store import get_experiment_store as _store

    batch_id = f"batch_{int(asyncio.get_running_loop().time() * 1000)}"

    async def _producer(send: Callable[[JSONObject], Awaitable[None]]) -> None:
        try:
            base = batch_config.base_config
            org_param = batch_config.organism_param_name
            results = []
            store = _store()

            for target in batch_config.target_organisms:
                params = dict(base.parameters)
                params[org_param] = target.organism

                org_config = ExperimentConfig(
                    site_id=base.site_id,
                    record_type=base.record_type,
                    search_name=base.search_name,
                    parameters=params,
                    positive_controls=target.positive_controls
                    or list(base.positive_controls),
                    negative_controls=target.negative_controls
                    or list(base.negative_controls),
                    controls_search_name=base.controls_search_name,
                    controls_param_name=base.controls_param_name,
                    controls_value_format=base.controls_value_format,
                    enable_cross_validation=base.enable_cross_validation,
                    k_folds=base.k_folds,
                    enrichment_types=list(base.enrichment_types),
                    name=f"{base.name} ({target.organism})",
                    description=base.description,
                    optimization_specs=(
                        copy.deepcopy(base.optimization_specs)
                        if base.optimization_specs
                        else None
                    ),
                    optimization_budget=base.optimization_budget,
                    optimization_objective=base.optimization_objective,
                    parameter_display_values=(
                        dict(base.parameter_display_values)
                        if base.parameter_display_values
                        else None
                    ),
                )

                try:
                    exp = await run_experiment(org_config, progress_callback=send)
                    exp.batch_id = batch_id
                    store.save(exp)
                    results.append(exp)
                except Exception as exc:
                    logger.error(
                        "Batch organism experiment failed",
                        organism=target.organism,
                        error=str(exc),
                    )

            await send(
                {
                    "type": "batch_complete",
                    "data": {
                        "batchId": batch_id,
                        "experiments": [experiment_to_json(e) for e in results],
                    },
                }
            )
        except Exception as exc:
            logger.error("Batch experiment failed", error=str(exc), exc_info=True)
            await send(
                {
                    "type": "batch_error",
                    "data": {"error": str(exc)},
                }
            )

    return sse_stream(_producer, {"batch_complete", "batch_error"})


def benchmark_sse_generator(
    base_config: ExperimentConfig,
    control_sets: list[tuple[str, list[str], list[str], str | None, bool]],
) -> AsyncIterator[str]:
    """SSE event stream for benchmark suite experiments running in parallel."""
    from veupath_chatbot.services.experiment.store import get_experiment_store as _store

    benchmark_id = f"bench_{int(asyncio.get_running_loop().time() * 1000)}"

    async def _producer(send: Callable[[JSONObject], Awaitable[None]]) -> None:
        try:

            async def _run_one(
                label: str,
                positives: list[str],
                negatives: list[str],
                control_set_id: str | None,
                is_primary: bool,
            ) -> Experiment | None:
                cfg = copy.deepcopy(base_config)
                cfg.positive_controls = positives
                cfg.negative_controls = negatives
                cfg.name = f"{base_config.name} [{label}]"
                cfg.control_set_id = control_set_id

                try:
                    exp = await run_experiment(cfg, progress_callback=send)
                    exp.benchmark_id = benchmark_id
                    exp.control_set_label = label
                    exp.is_primary_benchmark = is_primary
                    store = _store()
                    store.save(exp)
                    return exp
                except Exception as exc:
                    logger.error(
                        "Benchmark experiment failed",
                        label=label,
                        error=str(exc),
                    )
                    return None

            tasks = [
                _run_one(label, pos, neg, csid, primary)
                for label, pos, neg, csid, primary in control_sets
            ]
            results = await asyncio.gather(*tasks)
            completed = [r for r in results if r is not None]
            await send(
                {
                    "type": "benchmark_complete",
                    "data": {
                        "benchmarkId": benchmark_id,
                        "experiments": [experiment_to_json(e) for e in completed],
                    },
                }
            )
        except Exception as exc:
            logger.error("Benchmark suite failed", error=str(exc), exc_info=True)
            await send(
                {
                    "type": "benchmark_error",
                    "data": {"error": str(exc)},
                }
            )

    return sse_stream(_producer, {"benchmark_complete", "benchmark_error"})
