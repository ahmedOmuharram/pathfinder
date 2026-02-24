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
    BatchExperimentConfig,
    BatchOrganismTarget,
    ExperimentConfig,
    OptimizationSpec,
    experiment_summary_to_json,
    experiment_to_json,
)
from veupath_chatbot.transport.http.schemas.experiments import (
    AiAssistRequest,
    CreateBatchExperimentRequest,
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
    opt_specs = None
    if request.optimization_specs:
        opt_specs = [
            OptimizationSpec(
                name=s.name,
                type=s.type,
                min=s.min,
                max=s.max,
                step=s.step,
                choices=s.choices,
            )
            for s in request.optimization_specs
        ]
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
        optimization_specs=opt_specs,
        optimization_budget=request.optimization_budget,
        optimization_objective=request.optimization_objective or "balanced_accuracy",
        parameter_display_values=(
            {str(k): str(v) for k, v in request.parameter_display_values.items()}
            if request.parameter_display_values
            else None
        ),
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
        search_name=req.search_name,
        parameters=req.parameters,
        positive_controls=req.positive_controls,
        negative_controls=req.negative_controls,
        controls_search_name=req.controls_search_name,
        controls_param_name=req.controls_param_name,
        controls_value_format=req.controls_value_format,
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
    )


async def _batch_sse_generator(
    batch_config: BatchExperimentConfig,
) -> AsyncIterator[str]:
    """SSE event stream for cross-organism batch experiments."""
    import copy

    from veupath_chatbot.services.experiment.store import get_experiment_store as _store

    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    batch_id = f"batch_{int(asyncio.get_event_loop().time() * 1000)}"

    async def _progress_callback(event: JSONObject) -> None:
        await queue.put(event)

    async def _run() -> None:
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
                exp = await run_experiment(
                    org_config, progress_callback=_progress_callback
                )
                exp.batch_id = batch_id
                store.save(exp)
                results.append(exp)
            except Exception as exc:
                logger.error(
                    "Batch organism experiment failed",
                    organism=target.organism,
                    error=str(exc),
                )

        await queue.put(
            {
                "type": "batch_complete",
                "data": {
                    "batchId": batch_id,
                    "experiments": [experiment_to_json(e) for e in results],
                },
            }
        )

    task = asyncio.create_task(_run())
    try:
        while True:
            event = await queue.get()
            event_type = event.get("type", "experiment_progress")
            yield f"event: {event_type}\ndata: {json.dumps(event.get('data', {}))}\n\n"
            if event_type in ("batch_complete", "batch_error"):
                break
    finally:
        task.cancel()


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
        saw_end = False
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
                if event_type == "message_end":
                    saw_end = True
                yield f"event: {event_type}\ndata: {json.dumps(event.get('data', {}))}\n\n"
        except Exception as exc:
            logger.error("AI assist failed", error=str(exc), exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
        if not saw_end:
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
