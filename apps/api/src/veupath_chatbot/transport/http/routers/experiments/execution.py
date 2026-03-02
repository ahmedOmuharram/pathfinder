"""Experiment execution endpoints: create, batch, benchmark with SSE streaming."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.core.config import config_from_request
from veupath_chatbot.services.experiment.core.streaming import (
    batch_sse_generator,
    benchmark_sse_generator,
    experiment_sse_generator,
)
from veupath_chatbot.services.experiment.types import (
    BatchExperimentConfig,
    BatchOrganismTarget,
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

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


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
    config = config_from_request(request)
    return StreamingResponse(
        experiment_sse_generator(config),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
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
    base_config = config_from_request(request.base)
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
        batch_sse_generator(batch_config),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
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
    base_config = config_from_request(request.base)
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
        benchmark_sse_generator(base_config, control_sets),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
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
        headers=_SSE_HEADERS,
    )
