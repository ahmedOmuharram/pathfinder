"""Background task launchers for experiment execution — CQRS version.

Events are persisted to Redis Streams. Operations are registered in PostgreSQL.
"""

import asyncio
import copy
import json
from uuid import UUID, uuid4

from veupath_chatbot.persistence.repositories.stream import StreamRepository
from veupath_chatbot.persistence.repositories.user import UserRepository
from veupath_chatbot.persistence.session import async_session_factory
from veupath_chatbot.platform.errors import sanitize_error_for_client
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.redis import get_redis
from veupath_chatbot.platform.tasks import spawn
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.helpers import ProgressCallback
from veupath_chatbot.services.experiment.service import run_experiment
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import (
    BatchExperimentConfig,
    Experiment,
    ExperimentConfig,
    experiment_to_json,
)

logger = get_logger(__name__)

# Synthetic stream for experiment operations (experiments don't have
# a conversation stream — they share a fixed UUID).
_EXPERIMENT_STREAM_ID = UUID("00000000-0000-0000-0000-000000000001")
_EXPERIMENT_USER_ID = UUID("00000000-0000-0000-0000-000000000000")


async def _emit_to_redis(
    operation_id: str,
    event_type: str,
    event_data: JSONObject,
) -> None:
    """Emit a single event to the experiment Redis stream."""
    redis = get_redis()
    await redis.xadd(
        f"op:{operation_id}",
        {
            "op": operation_id.encode(),
            "type": event_type.encode(),
            "data": json.dumps(event_data, default=str).encode(),
        },
    )


def _make_progress_callback(
    operation_id: str,
) -> ProgressCallback:
    """Build a progress callback that emits events to a Redis stream."""

    async def _cb(evt: JSONObject) -> None:
        raw_type = evt.get("type", "experiment_progress")
        event_type = raw_type if isinstance(raw_type, str) else "experiment_progress"
        raw_data = evt.get("data")
        event_data = raw_data if isinstance(raw_data, dict) else evt
        await _emit_to_redis(operation_id, event_type, event_data)

    return _cb


async def _finalize_operation(operation_id: str, *, failed: bool) -> None:
    """Mark an experiment operation as completed or failed."""
    async with async_session_factory() as session:
        repo = StreamRepository(session)
        if failed:
            await repo.fail_operation(operation_id)
        else:
            await repo.complete_operation(operation_id)
        await session.commit()


async def _register_experiment_operation(operation_id: str, op_type: str) -> None:
    """Register an experiment operation in the DB before spawning.

    Ensures the experiment stream exists (creates it on first use) and
    registers the operation so the subscribe endpoint can find it
    immediately.
    """
    async with async_session_factory() as session:
        repo = StreamRepository(session)
        stream = await repo.get_by_id(_EXPERIMENT_STREAM_ID)
        if not stream:
            user_repo = UserRepository(session)
            await user_repo.get_or_create(_EXPERIMENT_USER_ID)
            await repo.create(
                user_id=_EXPERIMENT_USER_ID,
                site_id="system",
                stream_id=_EXPERIMENT_STREAM_ID,
                name="Experiments",
            )
        await repo.register_operation(operation_id, _EXPERIMENT_STREAM_ID, op_type)
        await session.commit()


async def start_experiment(
    config: ExperimentConfig, *, user_id: str | None = None
) -> str:
    """Launch a single experiment as a background task. Returns operation ID."""
    operation_id = f"op_{uuid4().hex[:12]}"
    await _register_experiment_operation(operation_id, "experiment")

    async def _run() -> None:
        failed = False
        try:
            result = await run_experiment(
                config,
                user_id=user_id,
                progress_callback=_make_progress_callback(operation_id),
            )
            await _emit_to_redis(
                operation_id,
                "experiment_complete",
                experiment_to_json(result),
            )
        except Exception as exc:
            failed = True
            logger.error("Experiment failed", error=str(exc), exc_info=True)
            await _emit_to_redis(operation_id, "experiment_error", {"error": sanitize_error_for_client(exc)})
        finally:
            await _emit_to_redis(operation_id, "experiment_end", {})
            await _finalize_operation(operation_id, failed=failed)

    spawn(_run())
    return operation_id


async def start_batch_experiment(
    batch_config: BatchExperimentConfig, *, user_id: str | None = None
) -> str:
    """Launch a batch experiment as a background task. Returns operation ID."""

    operation_id = f"op_{uuid4().hex[:12]}"
    batch_id = f"batch_{int(asyncio.get_running_loop().time() * 1000)}"
    await _register_experiment_operation(operation_id, "batch")

    async def _run() -> None:
        failed = False
        try:
            base = batch_config.base_config
            org_param = batch_config.organism_param_name
            results: list[Experiment] = []
            store = get_experiment_store()

            for target in batch_config.target_organisms:
                params = dict(base.parameters)
                params[org_param] = target.organism

                org_config = ExperimentConfig(
                    site_id=base.site_id,
                    record_type=base.record_type,
                    search_name=base.search_name,
                    parameters=params,
                    positive_controls=target.positive_controls
                    if target.positive_controls is not None
                    else list(base.positive_controls),
                    negative_controls=target.negative_controls
                    if target.negative_controls is not None
                    else list(base.negative_controls),
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
                    exp = await run_experiment(
                        org_config,
                        user_id=user_id,
                        progress_callback=_make_progress_callback(operation_id),
                    )
                    exp.batch_id = batch_id
                    store.save(exp)
                    results.append(exp)
                except Exception as exc:
                    logger.exception(
                        "Batch organism experiment failed",
                        organism=target.organism,
                        error=str(exc),
                    )

            await _emit_to_redis(
                operation_id,
                "batch_complete",
                {
                    "batchId": batch_id,
                    "experiments": [experiment_to_json(e) for e in results],
                },
            )
        except Exception as exc:
            failed = True
            logger.error("Batch experiment failed", error=str(exc), exc_info=True)
            await _emit_to_redis(operation_id, "batch_error", {"error": sanitize_error_for_client(exc)})
        finally:
            await _finalize_operation(operation_id, failed=failed)

    spawn(_run())
    return operation_id


async def start_benchmark(
    base_config: ExperimentConfig,
    control_sets: list[tuple[str, list[str], list[str], str | None, bool]],
    *,
    user_id: str | None = None,
) -> str:
    """Launch a benchmark suite as a background task. Returns operation ID."""

    operation_id = f"op_{uuid4().hex[:12]}"
    benchmark_id = f"bench_{int(asyncio.get_running_loop().time() * 1000)}"
    await _register_experiment_operation(operation_id, "benchmark")

    async def _run() -> None:
        failed = False
        try:

            async def _run_one(
                label: str,
                positives: list[str],
                negatives: list[str],
                control_set_id: str | None,
                *,
                is_primary: bool,
            ) -> Experiment | None:
                cfg = copy.deepcopy(base_config)
                cfg.positive_controls = positives
                cfg.negative_controls = negatives
                cfg.name = f"{base_config.name} [{label}]"
                cfg.control_set_id = control_set_id

                try:
                    exp = await run_experiment(
                        cfg,
                        user_id=user_id,
                        progress_callback=_make_progress_callback(operation_id),
                    )
                except Exception as exc:
                    logger.exception(
                        "Benchmark experiment failed",
                        label=label,
                        error=str(exc),
                    )
                    return None
                else:
                    exp.benchmark_id = benchmark_id
                    exp.control_set_label = label
                    exp.is_primary_benchmark = is_primary
                    store = get_experiment_store()
                    store.save(exp)
                    return exp

            tasks = [
                _run_one(label, pos, neg, csid, is_primary=primary)
                for label, pos, neg, csid, primary in control_sets
            ]
            results = await asyncio.gather(*tasks)
            completed = [r for r in results if r is not None]
            await _emit_to_redis(
                operation_id,
                "benchmark_complete",
                {
                    "benchmarkId": benchmark_id,
                    "experiments": [experiment_to_json(e) for e in completed],
                },
            )
        except Exception as exc:
            failed = True
            logger.error("Benchmark suite failed", error=str(exc), exc_info=True)
            await _emit_to_redis(operation_id, "benchmark_error", {"error": sanitize_error_for_client(exc)})
        finally:
            await _finalize_operation(operation_id, failed=failed)

    spawn(_run())
    return operation_id
