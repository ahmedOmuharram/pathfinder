"""CRUD endpoints for experiments: list, get, update, delete, importable strategies."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter
from pydantic import BaseModel, Field

from veupath_chatbot.platform.errors import NotFoundError
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import (
    experiment_summary_to_json,
    experiment_to_json,
)
from veupath_chatbot.transport.http.deps import ExperimentDep

router = APIRouter()


# -- Non-parametric routes (must be defined before /{experiment_id}) ----------


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


class CreateStrategyRequest(BaseModel):
    """Request to create a WDK strategy from a step tree."""

    site_id: str = Field(alias="siteId")
    record_type: str = Field(alias="recordType", default="transcript")
    step_tree: JSONValue = Field(alias="stepTree")
    name: str = Field(default="Seed strategy", max_length=200)
    description: str = Field(default="", max_length=2000)

    model_config = {"populate_by_name": True}


@router.post("/create-strategy")
async def create_strategy(request: CreateStrategyRequest) -> JSONObject:
    """Create a WDK strategy from a step tree definition.

    Materialises the step tree (creates WDK steps and a strategy) and returns
    the WDK strategy ID so it can be used with ``mode="import"`` experiments.
    """
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
    from veupath_chatbot.services.experiment.materialization import (
        _materialize_step_tree,
    )

    if not isinstance(request.step_tree, dict):
        raise NotFoundError(title="stepTree must be a JSON object")

    api = get_strategy_api(request.site_id)
    root = await _materialize_step_tree(api, request.step_tree, request.record_type)

    created = await api.create_strategy(
        step_tree=root,
        name=request.name,
        description=request.description,
        is_saved=True,
    )
    strategy_id: int | None = None
    if isinstance(created, dict):
        raw = created.get("id")
        if isinstance(raw, int):
            strategy_id = raw

    return {
        "wdkStrategyId": strategy_id,
        "rootStepId": root.step_id,
        "name": request.name,
    }


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
        "steps": cast(JSONValue, steps_array),
    }


# -- Parametric routes -------------------------------------------------------


@router.get("/")
async def list_experiments(
    siteId: str | None = None,
) -> list[JSONObject]:
    """List all experiments, optionally filtered by site."""
    store = get_experiment_store()
    experiments = await store.alist_all(site_id=siteId)
    return [experiment_summary_to_json(e) for e in experiments]


@router.get("/{experiment_id}")
async def get_experiment(exp: ExperimentDep) -> JSONObject:
    """Get full experiment details including all results."""
    return experiment_to_json(exp)


@router.patch("/{experiment_id}")
async def update_experiment(
    exp: ExperimentDep,
    request_body: dict[str, object],
) -> JSONObject:
    """Update experiment metadata (e.g. notes)."""
    if "notes" in request_body:
        exp.notes = (
            str(request_body["notes"]) if request_body["notes"] is not None else None
        )

    store = get_experiment_store()
    store.save(exp)
    return experiment_to_json(exp)


@router.delete("/{experiment_id}")
async def delete_experiment(exp: ExperimentDep) -> JSONObject:
    """Delete an experiment and clean up its WDK strategy."""
    from veupath_chatbot.services.experiment.materialization import (
        cleanup_experiment_strategy,
    )

    await cleanup_experiment_strategy(exp)

    store = get_experiment_store()
    await store.adelete(exp.id)
    return {"success": True}
