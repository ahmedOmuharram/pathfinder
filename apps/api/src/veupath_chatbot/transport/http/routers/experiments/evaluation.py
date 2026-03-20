"""Evaluation endpoints: re-evaluate, threshold-sweep, export."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.evaluation import re_evaluate
from veupath_chatbot.services.experiment.report import generate_experiment_report
from veupath_chatbot.services.experiment.sweep_service import (
    compute_sweep_values,
    generate_sweep_events,
    validate_sweep_parameter,
)
from veupath_chatbot.transport.http.deps import CurrentUser, ExperimentDep
from veupath_chatbot.transport.http.schemas.experiments import ThresholdSweepRequest

router = APIRouter()


@router.post("/{experiment_id}/re-evaluate")
async def re_evaluate_experiment(
    exp: ExperimentDep, user_id: CurrentUser
) -> JSONObject:
    """Re-run control evaluation against the (possibly modified) strategy."""
    return await re_evaluate(exp)


@router.post("/{experiment_id}/threshold-sweep")
async def threshold_sweep(
    exp: ExperimentDep,
    request: ThresholdSweepRequest,
    user_id: CurrentUser,
) -> StreamingResponse:
    """Sweep a parameter across a range and stream metrics as they complete."""
    validate_sweep_parameter(exp, request.parameter_name)
    sweep_values = compute_sweep_values(
        sweep_type=request.sweep_type,
        values=request.values,
        min_value=request.min_value,
        max_value=request.max_value,
        steps=request.steps,
    )

    return StreamingResponse(
        generate_sweep_events(
            exp=exp,
            param_name=request.parameter_name,
            sweep_type=request.sweep_type,
            sweep_values=sweep_values,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{experiment_id}/export")
async def get_experiment_report(
    exp: ExperimentDep, user_id: CurrentUser
) -> StreamingResponse:
    """Generate and return a self-contained HTML report for an experiment."""
    html_content = generate_experiment_report(exp)

    return StreamingResponse(
        iter([html_content]),
        media_type="text/html",
        headers={
            "Content-Disposition": f'attachment; filename="experiment-{exp.id}-report.html"',
        },
    )
