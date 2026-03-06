"""Experiment execution endpoints: create, batch, benchmark."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.security import limiter
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.core.streaming import (
    start_batch_experiment,
    start_benchmark,
    start_experiment,
)
from veupath_chatbot.services.experiment.types import (
    BatchExperimentConfig,
    BatchOrganismTarget,
)
from veupath_chatbot.transport.http.deps import (
    ControlSetRepo,
    CurrentUser,
    StreamRepo,
)
from veupath_chatbot.transport.http.schemas.experiments import (
    CreateBatchExperimentRequest,
    CreateBenchmarkRequest,
    CreateExperimentRequest,
)
from veupath_chatbot.transport.http.sse import SSE_HEADERS, sse_stream

from ._config import config_from_request

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/",
    status_code=202,
    responses={
        202: {
            "description": "Experiment launched as background task",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"operationId": {"type": "string"}},
                    }
                }
            },
        }
    },
)
@limiter.limit("20/minute")
async def create_experiment(
    request: Request,
    body: CreateExperimentRequest,
    user_id: CurrentUser,
) -> JSONResponse:
    """Create and run an experiment as a background task."""
    config = config_from_request(body)
    operation_id = await start_experiment(config, user_id=str(user_id))
    return JSONResponse({"operationId": operation_id}, status_code=202)


@router.post(
    "/batch",
    status_code=202,
    responses={
        202: {
            "description": "Batch experiment launched as background task",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"operationId": {"type": "string"}},
                    }
                }
            },
        }
    },
)
@limiter.limit("10/minute")
async def create_batch_experiment(
    request: Request,
    body: CreateBatchExperimentRequest,
    user_id: CurrentUser,
) -> JSONResponse:
    """Run the same search across multiple organisms as a background task."""
    base_config = config_from_request(body.base)
    batch_config = BatchExperimentConfig(
        base_config=base_config,
        organism_param_name=body.organism_param_name,
        target_organisms=[
            BatchOrganismTarget(
                organism=t.organism,
                positive_controls=t.positive_controls,
                negative_controls=t.negative_controls,
            )
            for t in body.target_organisms
        ],
    )
    operation_id = await start_batch_experiment(batch_config, user_id=str(user_id))
    return JSONResponse({"operationId": operation_id}, status_code=202)


@router.post(
    "/benchmark",
    status_code=202,
    responses={
        202: {
            "description": "Benchmark suite launched as background task",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"operationId": {"type": "string"}},
                    }
                }
            },
        }
    },
)
@limiter.limit("10/minute")
async def create_benchmark(
    request: Request,
    body: CreateBenchmarkRequest,
    user_id: CurrentUser,
) -> JSONResponse:
    """Run the same strategy against multiple control sets as a background task."""
    base_config = config_from_request(body.base)
    control_sets = [
        (
            cs.label,
            cs.positive_controls,
            cs.negative_controls,
            cs.control_set_id,
            cs.is_primary,
        )
        for cs in body.control_sets
    ]
    has_primary = any(cs.is_primary for cs in body.control_sets)
    if not has_primary and control_sets:
        control_sets[0] = (
            control_sets[0][0],
            control_sets[0][1],
            control_sets[0][2],
            control_sets[0][3],
            True,
        )

    operation_id = await start_benchmark(
        base_config, control_sets, user_id=str(user_id)
    )
    return JSONResponse({"operationId": operation_id}, status_code=202)


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
    stream_repo: StreamRepo,
    control_set_repo: ControlSetRepo,
) -> StreamingResponse:
    """Seed demo strategies and control sets across multiple VEuPathDB sites."""
    from veupath_chatbot.services.experiment.seed import run_seed

    async def _producer(send: Callable[[JSONObject], Awaitable[None]]) -> None:
        try:
            async for event in run_seed(
                user_id=user_id,
                stream_repo=stream_repo,
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
        headers=SSE_HEADERS,
    )
