"""Experiment Lab endpoints."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from veupath_chatbot.platform.errors import NotFoundError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.service import run_experiment
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import (
    ExperimentConfig,
    experiment_summary_to_json,
    experiment_to_json,
)
from veupath_chatbot.transport.http.schemas.experiments import (
    AiAssistRequest,
    CreateExperimentRequest,
    RunCrossValidationRequest,
    RunEnrichmentRequest,
)

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])
logger = get_logger(__name__)


async def _sse_generator(
    config: ExperimentConfig,
) -> AsyncIterator[str]:
    """SSE event stream for experiment execution."""
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()

    async def _progress_callback(event: JSONObject) -> None:
        await queue.put(event)

    async def _run() -> None:
        try:
            result = await run_experiment(config, progress_callback=_progress_callback)
            await queue.put(
                {
                    "type": "experiment_complete",
                    "data": experiment_to_json(result),
                }
            )
        except Exception as exc:
            logger.error("Experiment failed", error=str(exc), exc_info=True)
            await queue.put(
                {
                    "type": "experiment_error",
                    "data": {"error": str(exc)},
                }
            )
        finally:
            await queue.put({"type": "experiment_end", "data": {}})

    task = asyncio.create_task(_run())
    try:
        while True:
            event = await queue.get()
            event_type = event.get("type", "experiment_progress")
            yield f"event: {event_type}\ndata: {json.dumps(event.get('data', {}))}\n\n"
            if event_type == "experiment_end":
                break
    finally:
        task.cancel()


@router.post(
    "",
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
    config = ExperimentConfig(
        site_id=request.site_id,
        record_type=request.record_type,
        search_name=request.search_name,
        parameters=request.parameters,
        positive_controls=request.positive_controls,
        negative_controls=request.negative_controls,
        controls_search_name=request.controls_search_name,
        controls_param_name=request.controls_param_name,
        controls_value_format=request.controls_value_format,
        enable_cross_validation=request.enable_cross_validation,
        k_folds=request.k_folds,
        enrichment_types=list(request.enrichment_types),
        name=request.name,
        description=request.description,
    )
    return StreamingResponse(
        _sse_generator(config),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("")
async def list_experiments(
    siteId: str | None = None,
) -> list[JSONObject]:
    """List all experiments, optionally filtered by site."""
    store = get_experiment_store()
    experiments = store.list_all(site_id=siteId)
    return [experiment_summary_to_json(e) for e in experiments]


@router.get("/{experiment_id}")
async def get_experiment(experiment_id: str) -> JSONObject:
    """Get full experiment details including all results."""
    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")
    return experiment_to_json(exp)


@router.delete("/{experiment_id}")
async def delete_experiment(experiment_id: str) -> JSONObject:
    """Delete an experiment."""
    store = get_experiment_store()
    deleted = store.delete(experiment_id)
    if not deleted:
        raise NotFoundError(title="Experiment not found")
    return {"success": True}


@router.post("/{experiment_id}/cross-validate")
async def run_cv(
    experiment_id: str,
    request: RunCrossValidationRequest,
) -> JSONObject:
    """Run cross-validation on an existing experiment."""
    from veupath_chatbot.services.experiment.cross_validation import (
        run_cross_validation,
    )
    from veupath_chatbot.services.experiment.types import cv_result_to_json

    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

    cv = await run_cross_validation(
        site_id=exp.config.site_id,
        record_type=exp.config.record_type,
        search_name=exp.config.search_name,
        parameters=exp.config.parameters,
        controls_search_name=exp.config.controls_search_name,
        controls_param_name=exp.config.controls_param_name,
        positive_controls=exp.config.positive_controls,
        negative_controls=exp.config.negative_controls,
        controls_value_format=exp.config.controls_value_format,
        k=request.k_folds,
        full_metrics=exp.metrics,
    )
    exp.cross_validation = cv
    store.save(exp)
    return cv_result_to_json(cv)


@router.post("/{experiment_id}/enrich")
async def run_enrichment(
    experiment_id: str,
    request: RunEnrichmentRequest,
) -> list[JSONObject]:
    """Run enrichment analysis on an existing experiment's results."""
    from veupath_chatbot.services.experiment.enrichment import run_enrichment_analysis
    from veupath_chatbot.services.experiment.types import enrichment_result_to_json

    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

    results: list[JSONObject] = []
    for enrich_type in request.enrichment_types:
        er = await run_enrichment_analysis(
            site_id=exp.config.site_id,
            record_type=exp.config.record_type,
            search_name=exp.config.search_name,
            parameters=exp.config.parameters,
            analysis_type=enrich_type,
        )
        exp.enrichment_results.append(er)
        results.append(enrichment_result_to_json(er))

    store.save(exp)
    return results


@router.post(
    "/ai-assist",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE stream of AI assistant response",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def ai_assist(request: AiAssistRequest) -> StreamingResponse:
    """AI assistant for the experiment wizard.

    Streams a response with tool-use activity (web/literature search, site
    catalog lookup, gene lookup) to help the user with the current wizard step.
    """
    from veupath_chatbot.services.experiment.assistant import run_assistant

    history_raw = request.history if isinstance(request.history, list) else []
    history: list[JSONObject] = [h for h in history_raw if isinstance(h, dict)]

    async def _generate() -> AsyncIterator[str]:
        try:
            async for event in run_assistant(
                site_id=request.site_id,
                step=request.step,
                message=request.message,
                context=request.context,
                history=history,
                model_override=request.model,
            ):
                event_type = event.get("type", "message")
                yield f"event: {event_type}\ndata: {json.dumps(event.get('data', {}))}\n\n"
        except Exception as exc:
            logger.error("AI assist failed", error=str(exc), exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
        yield f"event: message_end\ndata: {json.dumps({})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
