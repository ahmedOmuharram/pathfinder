"""Experiment Lab endpoints."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import cast

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from veupath_chatbot.platform.errors import NotFoundError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.control_tests import (
    ControlValueFormat,
    run_positive_negative_controls,
)
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
    ThresholdSweepRequest,
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


@router.get("")
async def list_experiments(
    siteId: str | None = None,
) -> list[JSONObject]:
    """List all experiments, optionally filtered by site."""
    store = get_experiment_store()
    experiments = store.list_all(site_id=siteId)
    return [experiment_summary_to_json(e) for e in experiments]


@router.get("/importable-strategies")
async def list_importable_strategies(siteId: str) -> list[JSONObject]:
    """List Pathfinder strategies available for import into experiments."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
    from veupath_chatbot.integrations.veupathdb.strategy_api import (
        is_internal_wdk_strategy_name,
    )

    api = get_strategy_api(siteId)
    raw = await api.list_strategies()
    results: list[JSONObject] = []
    if not isinstance(raw, list):
        return results
    for strat in raw:
        if not isinstance(strat, dict):
            continue
        name = strat.get("name")
        if isinstance(name, str) and is_internal_wdk_strategy_name(name):
            continue
        results.append(
            {
                "wdkStrategyId": strat.get("strategyId"),
                "name": strat.get("name", ""),
                "recordType": strat.get("recordClassName"),
                "stepCount": strat.get("leafAndTransformStepCount"),
                "estimatedSize": strat.get("estimatedSize"),
                "lastModified": strat.get("lastModified"),
                "isSaved": strat.get("isSaved", False),
            }
        )
    return results


@router.get("/importable-strategies/{strategy_id}/details")
async def get_strategy_details(strategy_id: int, siteId: str) -> JSONObject:
    """Fetch full strategy step tree for import into the multi-step builder.

    The WDK ``GET /strategies/{id}`` response includes:
    - ``stepTree``: recursive tree with only ``stepId`` / ``primaryInput`` / ``secondaryInput``
    - ``steps``: a **map** (object keyed by string step ID) of full step data
      including ``searchName``, ``searchConfig.parameters``, ``customName``, etc.

    This endpoint flattens the steps map into an array and enriches the
    step tree so the frontend can display search names and parameters.
    """
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    api = get_strategy_api(siteId)
    raw = await api.get_strategy(strategy_id)
    if not isinstance(raw, dict):
        raise NotFoundError(title="Strategy not found")

    step_tree = raw.get("stepTree")
    raw_steps = raw.get("steps", {})
    name = raw.get("name", "")
    record_type = raw.get("recordClassName", "")

    # WDK returns steps as { "stepId_string": { step_data }, ... }
    steps_map: dict[str, JSONObject] = {}
    if isinstance(raw_steps, dict):
        for k, v in raw_steps.items():
            if isinstance(v, dict):
                steps_map[str(k)] = v
    elif isinstance(raw_steps, list):
        for v in raw_steps:
            if isinstance(v, dict):
                sid = v.get("id") or v.get("stepId")
                if sid is not None:
                    steps_map[str(sid)] = v

    # Enrich the step tree nodes with search data from the steps map
    def _enrich_tree(node: JSONObject) -> JSONObject:
        if not isinstance(node, dict):
            return node
        sid = str(node.get("stepId", ""))
        step_data = steps_map.get(sid, {})
        search_config = (
            step_data.get("searchConfig") if isinstance(step_data, dict) else {}
        )
        if not isinstance(search_config, dict):
            search_config = {}

        enriched: JSONObject = {
            "stepId": node.get("stepId"),
            "searchName": step_data.get("searchName", "")
            if isinstance(step_data, dict)
            else "",
            "displayName": (
                step_data.get("customName")
                or step_data.get("displayName")
                or step_data.get("searchName", "")
            )
            if isinstance(step_data, dict)
            else "",
            "parameters": search_config.get("parameters", {}),
            "recordType": step_data.get("recordClassName", record_type)
            if isinstance(step_data, dict)
            else record_type,
            "estimatedSize": step_data.get("estimatedSize")
            if isinstance(step_data, dict)
            else None,
        }
        pi = node.get("primaryInput")
        si = node.get("secondaryInput")
        if isinstance(pi, dict):
            enriched["primaryInput"] = _enrich_tree(pi)
        if isinstance(si, dict):
            enriched["secondaryInput"] = _enrich_tree(si)
        return enriched

    enriched_tree = (
        _enrich_tree(step_tree) if isinstance(step_tree, dict) else step_tree
    )

    # Also return a flat array of steps for convenience
    steps_array: list[JSONObject] = list(steps_map.values())

    return {
        "wdkStrategyId": strategy_id,
        "name": name,
        "recordType": record_type,
        "stepTree": enriched_tree,
        "steps": steps_array,
    }


@router.get("/{experiment_id}")
async def get_experiment(experiment_id: str) -> JSONObject:
    """Get full experiment details including all results."""
    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")
    return experiment_to_json(exp)


@router.patch("/{experiment_id}")
async def update_experiment(
    experiment_id: str,
    request_body: dict[str, object],
) -> JSONObject:
    """Update experiment metadata (e.g. notes)."""
    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

    if "notes" in request_body:
        exp.notes = (
            str(request_body["notes"]) if request_body["notes"] is not None else None
        )

    store.save(exp)
    return experiment_to_json(exp)


@router.delete("/{experiment_id}")
async def delete_experiment(experiment_id: str) -> JSONObject:
    """Delete an experiment and clean up its WDK strategy."""
    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

    from veupath_chatbot.services.experiment.service import cleanup_experiment_strategy

    await cleanup_experiment_strategy(exp)

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
        enable_tree_optimization=req.enable_tree_optimization,
        tree_optimization_budget=req.tree_optimization_budget,
        optimize_operators=req.optimize_operators,
        optimize_orthologs=req.optimize_orthologs,
        ortholog_organisms=req.ortholog_organisms,
        optimize_structure=req.optimize_structure,
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


@router.get("/{experiment_id}/results/attributes")
async def get_experiment_attributes(experiment_id: str) -> JSONObject:
    """Get available attributes for an experiment's record type."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

    api = get_strategy_api(exp.config.site_id)
    info = await api.get_record_type_info(exp.config.record_type)

    attributes: list[JSONObject] = []
    attrs_raw = info.get("attributes") or info.get("attributesMap") or {}
    if isinstance(attrs_raw, dict):
        for name, meta in attrs_raw.items():
            if isinstance(meta, dict):
                attributes.append(
                    {
                        "name": str(name),
                        "displayName": meta.get("displayName", name),
                        "help": meta.get("help"),
                        "type": meta.get("type"),
                        "isDisplayable": meta.get("isDisplayable", True),
                    }
                )
    elif isinstance(attrs_raw, list):
        for meta in attrs_raw:
            if isinstance(meta, dict):
                attr_name = str(meta.get("name", ""))
                attributes.append(
                    {
                        "name": attr_name,
                        "displayName": meta.get("displayName", attr_name),
                        "help": meta.get("help"),
                        "type": meta.get("type"),
                        "isDisplayable": meta.get("isDisplayable", True),
                    }
                )

    return {
        "attributes": cast(JSONValue, attributes),
        "recordType": exp.config.record_type,
    }


@router.get("/{experiment_id}/results/records")
async def get_experiment_records(
    experiment_id: str,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    dir: str = "ASC",
    attributes: str | None = None,
) -> JSONObject:
    """Get paginated result records for an experiment.

    Requires a persisted WDK strategy (``wdkStepId`` must be set).
    """
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

    if not exp.wdk_step_id or not exp.wdk_strategy_id:
        raise NotFoundError(
            title="No WDK strategy",
            detail="This experiment has no persisted WDK strategy for result browsing.",
        )

    api = get_strategy_api(exp.config.site_id)

    attr_list: list[str] | None = None
    if attributes:
        attr_list = [a.strip() for a in attributes.split(",") if a.strip()]

    sorting: list[JSONObject] | None = None
    if sort:
        sorting = [{"attributeName": sort, "direction": dir.upper()}]

    answer = await api.get_step_records(
        step_id=exp.wdk_step_id,
        attributes=attr_list,
        pagination={"offset": offset, "numRecords": limit},
        sorting=sorting,
    )

    tp_ids = {g.id for g in exp.true_positive_genes}
    fp_ids = {g.id for g in exp.false_positive_genes}
    fn_ids = {g.id for g in exp.false_negative_genes}
    tn_ids = {g.id for g in exp.true_negative_genes}

    records = answer.get("records", [])
    classified_records: list[JSONObject] = []
    if isinstance(records, list):
        for rec in records:
            if not isinstance(rec, dict):
                continue
            gene_id = _extract_pk(rec)
            classification: str | None = None
            if gene_id:
                if gene_id in tp_ids:
                    classification = "TP"
                elif gene_id in fp_ids:
                    classification = "FP"
                elif gene_id in fn_ids:
                    classification = "FN"
                elif gene_id in tn_ids:
                    classification = "TN"
            classified_records.append({**rec, "_classification": classification})

    meta = answer.get("meta", {})
    return {"records": cast(JSONValue, classified_records), "meta": meta}


@router.post("/{experiment_id}/results/record")
async def get_experiment_record_detail(
    experiment_id: str,
    request_body: dict[str, object],
) -> JSONObject:
    """Get a single record's full details by primary key.

    Expects ``{"primaryKey": [{"name": "...", "value": "..."}, ...]}``
    (or ``primary_key``) matching the record type's primary key structure.
    If the client sends fewer PK parts than the record type requires (e.g. only
    ``source_id`` for gene), missing parts such as ``project_id`` are filled
    from the site so WDK accepts the request.
    """
    from veupath_chatbot.integrations.veupathdb.factory import (
        get_site,
        get_strategy_api,
    )

    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

    raw_pk = request_body.get("primaryKey") or request_body.get("primary_key") or []
    if not isinstance(raw_pk, list) or not raw_pk:
        raise NotFoundError(title="Invalid primary key: must be a non-empty array")

    pk_parts: list[JSONObject] = [
        {"name": str(part.get("name", "")), "value": str(part.get("value", ""))}
        for part in raw_pk
        if isinstance(part, dict)
    ]

    api = get_strategy_api(exp.config.site_id)
    info = await api.get_record_type_info(exp.config.record_type)

    # WDK requires all primary key columns. Step reports sometimes return only
    # the first part (e.g. source_id). Fill missing parts (e.g. project_id).
    pk_refs = info.get("primaryKeyColumnRefs") or info.get("primaryKey") or []
    if isinstance(pk_refs, list) and len(pk_parts) < len(pk_refs):
        names_sent = {p.get("name") for p in pk_parts if isinstance(p, dict)}
        site = get_site(exp.config.site_id)
        for col in pk_refs:
            if not isinstance(col, str) or col in names_sent:
                continue
            if col == "project_id":
                pk_parts.append({"name": "project_id", "value": site.project_id})
                break
            # Other missing columns left as-is; WDK will validate.

    attrs_raw = info.get("attributes") or info.get("attributesMap") or {}
    attr_names: list[str] = []
    if isinstance(attrs_raw, dict):
        attr_names = [
            str(name)
            for name, meta in attrs_raw.items()
            if isinstance(meta, dict) and meta.get("isDisplayable", True)
        ]
    elif isinstance(attrs_raw, list):
        attr_names = [
            str(meta.get("name", ""))
            for meta in attrs_raw
            if isinstance(meta, dict) and meta.get("isDisplayable", True)
        ]

    return await api.get_single_record(
        record_type=exp.config.record_type,
        primary_key=pk_parts,
        attributes=attr_names if attr_names else None,
    )


@router.get("/{experiment_id}/strategy")
async def get_experiment_strategy(experiment_id: str) -> JSONObject:
    """Get the WDK strategy tree for an experiment."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")
    if not exp.wdk_strategy_id:
        raise NotFoundError(
            title="No WDK strategy",
            detail="This experiment has no persisted WDK strategy.",
        )

    api = get_strategy_api(exp.config.site_id)
    return await api.get_strategy(exp.wdk_strategy_id)


@router.get("/{experiment_id}/results/distributions/{attribute_name}")
async def get_experiment_distribution(
    experiment_id: str,
    attribute_name: str,
) -> JSONObject:
    """Get distribution data for an attribute using filter summary."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")
    if not exp.wdk_step_id:
        raise NotFoundError(title="No WDK strategy for this experiment")

    api = get_strategy_api(exp.config.site_id)
    return await api.get_filter_summary(exp.wdk_step_id, attribute_name)


@router.get("/{experiment_id}/analyses/types")
async def get_experiment_analysis_types(experiment_id: str) -> JSONObject:
    """List available WDK step analysis types for an experiment."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")
    if not exp.wdk_step_id:
        raise NotFoundError(title="No WDK strategy for this experiment")

    api = get_strategy_api(exp.config.site_id)
    types = await api.list_analysis_types(exp.wdk_step_id)
    return {"analysisTypes": types}


@router.post("/{experiment_id}/analyses/run")
async def run_experiment_analysis(
    experiment_id: str,
    request_body: dict[str, object],
) -> JSONObject:
    """Create and run a WDK step analysis on the experiment's step."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")
    if not exp.wdk_step_id:
        raise NotFoundError(title="No WDK strategy for this experiment")

    api = get_strategy_api(exp.config.site_id)
    analysis_name = str(request_body.get("analysisName", ""))
    raw_params = request_body.get("parameters", {})
    parameters: JSONObject = raw_params if isinstance(raw_params, dict) else {}

    result = await api.run_step_analysis(
        step_id=exp.wdk_step_id,
        analysis_type=analysis_name,
        parameters=parameters,
    )
    return result


@router.post("/{experiment_id}/refine")
async def refine_experiment(
    experiment_id: str,
    request_body: dict[str, object],
) -> JSONObject:
    """Add a step to the experiment's strategy (combine, transform, etc.)."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
    from veupath_chatbot.integrations.veupathdb.strategy_api import StepTreeNode

    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")
    if not exp.wdk_strategy_id or not exp.wdk_step_id:
        raise NotFoundError(title="No WDK strategy for this experiment")

    api = get_strategy_api(exp.config.site_id)
    action = str(request_body.get("action", ""))
    record_type = exp.config.record_type

    if action == "combine":
        search_name = str(request_body.get("searchName", ""))
        raw_params = request_body.get("parameters", {})
        parameters: JSONObject = raw_params if isinstance(raw_params, dict) else {}
        operator = str(request_body.get("operator", "INTERSECT"))

        new_step = await api.create_step(
            record_type=record_type,
            search_name=search_name,
            parameters=parameters,
            custom_name=f"Refinement: {search_name}",
        )
        new_step_id = new_step.get("id") if isinstance(new_step, dict) else None
        if not isinstance(new_step_id, int):
            raise NotFoundError(title="Failed to create new step")

        combined = await api.create_combined_step(
            primary_step_id=exp.wdk_step_id,
            secondary_step_id=new_step_id,
            boolean_operator=operator,
            record_type=record_type,
            custom_name=f"{operator} refinement",
        )
        combined_id = combined.get("id") if isinstance(combined, dict) else None
        if not isinstance(combined_id, int):
            raise NotFoundError(title="Failed to create combined step")

        new_tree = StepTreeNode(
            combined_id,
            primary_input=StepTreeNode(exp.wdk_step_id),
            secondary_input=StepTreeNode(new_step_id),
        )
        await api.update_strategy(exp.wdk_strategy_id, step_tree=new_tree)
        exp.wdk_step_id = combined_id
        store.save(exp)

        return {"success": True, "newStepId": combined_id}

    elif action == "transform":
        transform_name = str(request_body.get("transformName", ""))
        raw_t_params = request_body.get("parameters", {})
        t_parameters: JSONObject = (
            raw_t_params if isinstance(raw_t_params, dict) else {}
        )

        new_step = await api.create_transform_step(
            input_step_id=exp.wdk_step_id,
            transform_name=transform_name,
            parameters=t_parameters,
            record_type=record_type,
            custom_name=f"Transform: {transform_name}",
        )
        new_step_id = new_step.get("id") if isinstance(new_step, dict) else None
        if not isinstance(new_step_id, int):
            raise NotFoundError(title="Failed to create transform step")

        new_tree = StepTreeNode(
            new_step_id,
            primary_input=StepTreeNode(exp.wdk_step_id),
        )
        await api.update_strategy(exp.wdk_strategy_id, step_tree=new_tree)
        exp.wdk_step_id = new_step_id
        store.save(exp)

        return {"success": True, "newStepId": new_step_id}

    return {"success": False, "error": f"Unknown action: {action}"}


@router.post("/{experiment_id}/re-evaluate")
async def re_evaluate_experiment(experiment_id: str) -> JSONObject:
    """Re-run control evaluation against the (possibly modified) strategy."""
    from veupath_chatbot.services.experiment.metrics import metrics_from_control_result
    from veupath_chatbot.services.experiment.types import experiment_to_json

    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

    result = await run_positive_negative_controls(
        site_id=exp.config.site_id,
        record_type=exp.config.record_type,
        target_search_name=exp.config.search_name,
        target_parameters=exp.config.parameters,
        controls_search_name=exp.config.controls_search_name,
        controls_param_name=exp.config.controls_param_name,
        positive_controls=exp.config.positive_controls or None,
        negative_controls=exp.config.negative_controls or None,
        controls_value_format=exp.config.controls_value_format,  # type: ignore[arg-type]
    )

    from veupath_chatbot.services.experiment.service import (
        _extract_gene_list,
        _extract_id_set,
    )

    metrics = metrics_from_control_result(result)
    exp.metrics = metrics
    exp.true_positive_genes = _extract_gene_list(result, "positive", "intersectionIds")
    exp.false_negative_genes = _extract_gene_list(
        result, "positive", "missingIdsSample"
    )
    exp.false_positive_genes = _extract_gene_list(result, "negative", "intersectionIds")
    exp.true_negative_genes = _extract_gene_list(
        result,
        "negative",
        "missingIdsSample",
        fallback_from_controls=True,
        all_controls=exp.config.negative_controls,
        hit_ids=_extract_id_set(result, "negative", "intersectionIds"),
    )
    store.save(exp)

    return experiment_to_json(exp)


@router.post("/{experiment_id}/threshold-sweep")
async def threshold_sweep(
    experiment_id: str,
    request: ThresholdSweepRequest,
) -> JSONObject:
    """Sweep a numeric parameter across a range and compute metrics at each point."""
    from veupath_chatbot.services.experiment.metrics import metrics_from_control_result

    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

    param_name = request.parameter_name
    if param_name not in exp.config.parameters:
        raise NotFoundError(
            title="Parameter not found",
            detail=f"Parameter '{param_name}' is not in this experiment's config.",
        )

    step_size = (request.max_value - request.min_value) / max(request.steps - 1, 1)
    values = [request.min_value + i * step_size for i in range(request.steps)]

    points: list[JSONObject] = []
    for val in values:
        modified_params = dict(exp.config.parameters)
        modified_params[param_name] = str(val)

        try:
            result = await run_positive_negative_controls(
                site_id=exp.config.site_id,
                record_type=exp.config.record_type,
                target_search_name=exp.config.search_name,
                target_parameters=modified_params,
                controls_search_name=exp.config.controls_search_name,
                controls_param_name=exp.config.controls_param_name,
                positive_controls=exp.config.positive_controls or None,
                negative_controls=exp.config.negative_controls or None,
                controls_value_format=exp.config.controls_value_format,
            )
            m = metrics_from_control_result(result)
            points.append(
                {
                    "value": val,
                    "metrics": {
                        "sensitivity": round(m.sensitivity, 4),
                        "specificity": round(m.specificity, 4),
                        "precision": round(m.precision, 4),
                        "f1Score": round(m.f1_score, 4),
                        "mcc": round(m.mcc, 4),
                        "balancedAccuracy": round(m.balanced_accuracy, 4),
                        "totalResults": m.total_results,
                        "falsePositiveRate": round(m.false_positive_rate, 4),
                    },
                }
            )
        except Exception as exc:
            logger.warning(
                "Threshold sweep point failed",
                param=param_name,
                value=val,
                error=str(exc),
            )
            points.append({"value": val, "metrics": None, "error": str(exc)})

    return {"parameter": param_name, "points": cast(JSONValue, points)}


@router.post("/{experiment_id}/step-contributions")
async def step_contributions(
    experiment_id: str,
    body: dict[str, object],
) -> JSONObject:
    """Analyse per-step contribution to overall result for multi-step experiments.

    Evaluates controls against each leaf step individually to show how much
    each step contributes to the final strategy result.
    """
    store = get_experiment_store()
    exp = store.get(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

    step_tree_raw = body.get("stepTree")
    if not step_tree_raw or not isinstance(step_tree_raw, dict):
        return {"contributions": []}

    def _extract_leaves(node: dict[str, object]) -> list[dict[str, object]]:
        leaves: list[dict[str, object]] = []
        pi = node.get("primaryInput")
        si = node.get("secondaryInput")
        if isinstance(pi, dict):
            leaves.extend(_extract_leaves(pi))
        if isinstance(si, dict):
            leaves.extend(_extract_leaves(si))
        if not isinstance(pi, dict) and not isinstance(si, dict):
            leaves.append(node)
        return leaves

    leaves = _extract_leaves(step_tree_raw)
    contributions: list[JSONObject] = []

    cvf = exp.config.controls_value_format
    _valid_formats: set[ControlValueFormat] = {"newline", "json_list", "comma"}
    controls_format: ControlValueFormat = (
        cast(ControlValueFormat, cvf) if cvf in _valid_formats else "newline"
    )

    for leaf in leaves:
        search_name = leaf.get("searchName")
        if not isinstance(search_name, str) or not search_name:
            continue
        params = leaf.get("parameters")
        if not isinstance(params, dict):
            params = {}
        display_name = leaf.get("displayName") or search_name

        try:
            result = await run_positive_negative_controls(
                site_id=exp.config.site_id,
                record_type=exp.config.record_type,
                target_search_name=search_name,
                target_parameters=params,
                controls_search_name=exp.config.controls_search_name,
                controls_param_name=exp.config.controls_param_name,
                positive_controls=exp.config.positive_controls or None,
                negative_controls=exp.config.negative_controls or None,
                controls_value_format=controls_format,
            )
            target_data = result.get("target") or {}
            target_dict = target_data if isinstance(target_data, dict) else {}
            raw_count = target_dict.get("resultCount")
            total = int(raw_count) if isinstance(raw_count, (int, float)) else 0

            pos_data = result.get("positive") or {}
            pos_dict = pos_data if isinstance(pos_data, dict) else {}
            raw_pos_hits = pos_dict.get("intersectionCount")
            pos_hits = (
                int(raw_pos_hits) if isinstance(raw_pos_hits, (int, float)) else 0
            )

            neg_data = result.get("negative") or {}
            neg_dict = neg_data if isinstance(neg_data, dict) else {}
            raw_neg_hits = neg_dict.get("intersectionCount")
            neg_hits = (
                int(raw_neg_hits) if isinstance(raw_neg_hits, (int, float)) else 0
            )

            total_pos = (
                len(exp.config.positive_controls) if exp.config.positive_controls else 0
            )
            total_neg = (
                len(exp.config.negative_controls) if exp.config.negative_controls else 0
            )
            contributions.append(
                {
                    "stepName": str(display_name),
                    "stepSearchName": search_name,
                    "totalResults": total,
                    "positiveControlHits": pos_hits,
                    "negativeControlHits": neg_hits,
                    "positiveRecall": round(pos_hits / max(total_pos, 1), 4),
                    "negativeRecall": round(neg_hits / max(total_neg, 1), 4),
                }
            )
        except Exception as exc:
            logger.warning(
                "Step contribution analysis failed",
                step=search_name,
                error=str(exc),
            )
            contributions.append(
                {
                    "stepName": str(display_name),
                    "stepSearchName": search_name,
                    "totalResults": 0,
                    "positiveControlHits": 0,
                    "negativeControlHits": 0,
                    "positiveRecall": 0,
                    "negativeRecall": 0,
                }
            )

    return {"contributions": cast(JSONValue, contributions)}


def _extract_pk(record: JSONObject) -> str | None:
    """Extract primary key string from a WDK record."""
    pk = record.get("id")
    if isinstance(pk, list) and pk:
        first = pk[0]
        if isinstance(first, dict):
            val = first.get("value")
            if isinstance(val, str):
                return val.strip()
    return None


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
