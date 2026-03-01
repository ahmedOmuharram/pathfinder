"""Experiment execution endpoints: create, batch, benchmark with SSE streaming."""

from __future__ import annotations

import asyncio
import copy
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import cast

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.service import run_experiment
from veupath_chatbot.services.experiment.types import (
    BatchExperimentConfig,
    BatchOrganismTarget,
    ControlValueFormat,
    Experiment,
    ExperimentConfig,
    OperatorKnob,
    OptimizationSpec,
    ThresholdKnob,
    experiment_to_json,
)
from veupath_chatbot.transport.http.deps import (
    ControlSetRepo,
    CurrentUser,
    StrategyRepo,
)
from veupath_chatbot.transport.http.schemas.experiments import (
    CreateBatchExperimentRequest,
    CreateBenchmarkRequest,
    CreateExperimentRequest,
)
from veupath_chatbot.transport.http.sse import sse_stream

router = APIRouter()
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config_from_request(req: CreateExperimentRequest) -> ExperimentConfig:
    """Build :class:`ExperimentConfig` from a create request DTO."""
    opt_specs = None
    if req.optimization_specs:
        opt_specs = [
            OptimizationSpec(
                name=s.name,
                type=s.type,
                min=s.min,
                max=s.max,
                step=s.step,
                choices=s.choices,
            )
            for s in req.optimization_specs
        ]
    return ExperimentConfig(
        site_id=req.site_id,
        record_type=req.record_type,
        mode=req.mode,
        search_name=req.search_name,
        parameters=req.parameters,
        step_tree=req.step_tree,
        source_strategy_id=req.source_strategy_id,
        optimization_target_step=req.optimization_target_step,
        positive_controls=req.positive_controls,
        negative_controls=req.negative_controls,
        controls_search_name=req.controls_search_name,
        controls_param_name=req.controls_param_name,
        controls_value_format=cast(ControlValueFormat, req.controls_value_format),
        enable_cross_validation=req.enable_cross_validation,
        k_folds=req.k_folds,
        enrichment_types=list(req.enrichment_types),
        name=req.name,
        description=req.description,
        optimization_specs=opt_specs,
        optimization_budget=req.optimization_budget,
        optimization_objective=req.optimization_objective or "balanced_accuracy",
        parameter_display_values=(
            {str(k): str(v) for k, v in req.parameter_display_values.items()}
            if req.parameter_display_values
            else None
        ),
        enable_step_analysis=req.enable_step_analysis,
        step_analysis_phases=(
            req.step_analysis_phases
            if req.step_analysis_phases
            else [
                "step_evaluation",
                "operator_comparison",
                "contribution",
                "sensitivity",
            ]
        ),
        control_set_id=req.control_set_id,
        threshold_knobs=[
            ThresholdKnob(
                step_id=k.step_id,
                param_name=k.param_name,
                min_val=k.min_val,
                max_val=k.max_val,
                step_size=k.step_size,
            )
            for k in (req.threshold_knobs or [])
        ]
        or None,
        operator_knobs=[
            OperatorKnob(
                combine_node_id=k.combine_node_id,
                options=k.options,
            )
            for k in (req.operator_knobs or [])
        ]
        or None,
        tree_optimization_objective=req.tree_optimization_objective,
        tree_optimization_budget=req.tree_optimization_budget,
        max_list_size=req.max_list_size,
        sort_attribute=req.sort_attribute,
        sort_direction=req.sort_direction,
        parent_experiment_id=req.parent_experiment_id,
    )


# ---------------------------------------------------------------------------
# SSE generators
# ---------------------------------------------------------------------------


def _sse_generator(
    config: ExperimentConfig,
) -> AsyncIterator[str]:
    """SSE event stream for experiment execution."""

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


def _batch_sse_generator(
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


def _benchmark_sse_generator(
    base_config: ExperimentConfig,
    control_sets: list[tuple[str, list[str], list[str], str | None, bool]],
) -> AsyncIterator[str]:
    """SSE event stream for benchmark suite experiments running in parallel."""
    from veupath_chatbot.services.experiment.service import run_experiment
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


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE stream of experiment progress",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def create_experiment(request: CreateExperimentRequest) -> StreamingResponse:
    """Create and run an experiment with SSE progress streaming."""
    config = _config_from_request(request)
    return StreamingResponse(
        _sse_generator(config),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/batch",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE stream of batch experiment progress",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def create_batch_experiment(
    request: CreateBatchExperimentRequest,
) -> StreamingResponse:
    """Run the same search across multiple organisms with SSE progress."""
    base_config = _config_from_request(request.base)
    batch_config = BatchExperimentConfig(
        base_config=base_config,
        organism_param_name=request.organism_param_name,
        target_organisms=[
            BatchOrganismTarget(
                organism=t.organism,
                positive_controls=t.positive_controls,
                negative_controls=t.negative_controls,
            )
            for t in request.target_organisms
        ],
    )
    return StreamingResponse(
        _batch_sse_generator(batch_config),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/benchmark",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE stream of benchmark suite progress",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def create_benchmark(
    request: CreateBenchmarkRequest,
) -> StreamingResponse:
    """Run the same strategy against multiple control sets in parallel with SSE."""
    base_config = _config_from_request(request.base)
    control_sets = [
        (
            cs.label,
            cs.positive_controls,
            cs.negative_controls,
            cs.control_set_id,
            cs.is_primary,
        )
        for cs in request.control_sets
    ]
    has_primary = any(cs.is_primary for cs in request.control_sets)
    if not has_primary:
        control_sets[0] = (
            control_sets[0][0],
            control_sets[0][1],
            control_sets[0][2],
            control_sets[0][3],
            True,
        )

    return StreamingResponse(
        _benchmark_sse_generator(base_config, control_sets),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/seed",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE stream of seed strategy/control-set progress",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def seed_strategies(
    user_id: CurrentUser,
    strategy_repo: StrategyRepo,
    control_set_repo: ControlSetRepo,
) -> StreamingResponse:
    """Seed demo strategies and control sets across multiple VEuPathDB sites."""
    from veupath_chatbot.services.experiment.seed import run_seed

    async def _producer(send: Callable[[JSONObject], Awaitable[None]]) -> None:
        try:
            async for event in run_seed(
                user_id=user_id,
                strategy_repo=strategy_repo,
                control_set_repo=control_set_repo,
            ):
                await send(event)
        except Exception as exc:
            logger.error("Seed failed", error=str(exc), exc_info=True)
            await send(
                {
                    "type": "seed_complete",
                    "data": {"error": str(exc), "message": f"Seed failed: {exc}"},
                }
            )

    return StreamingResponse(
        sse_stream(_producer, {"seed_complete"}),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
