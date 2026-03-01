"""Results endpoints: records, record detail, attributes, strategy, distributions, analyses, refine."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter

from veupath_chatbot.platform.errors import NotFoundError
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.transport.http.schemas.experiments import (
    RefineRequest,
    RunAnalysisRequest,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SORTABLE_WDK_TYPES = {"number", "float", "integer", "double"}

_SCORE_ATTRIBUTE_KEYWORDS = {
    "score",
    "e_value",
    "evalue",
    "bit_score",
    "bitscore",
    "p_value",
    "pvalue",
    "fold_change",
    "log_fc",
    "confidence",
}


def _is_sortable(attr_type: str | None) -> bool:
    """Return ``True`` if a WDK attribute type supports numeric sorting."""
    if not attr_type:
        return False
    return attr_type.lower() in _SORTABLE_WDK_TYPES


def _is_suggested_score(name: str) -> bool:
    """Heuristic: flag well-known score attributes as suggested for ranking."""
    lower = name.lower()
    return any(kw in lower for kw in _SCORE_ATTRIBUTE_KEYWORDS)


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


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get("/{experiment_id}/results/attributes")
async def get_experiment_attributes(experiment_id: str) -> JSONObject:
    """Get available attributes for an experiment's record type."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    store = get_experiment_store()
    exp = await store.aget(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

    api = get_strategy_api(exp.config.site_id)
    info = await api.get_record_type_info(exp.config.record_type)

    attributes: list[JSONObject] = []
    attrs_raw = info.get("attributes") or info.get("attributesMap") or {}
    if isinstance(attrs_raw, dict):
        for name, meta in attrs_raw.items():
            if isinstance(meta, dict):
                raw_type = meta.get("type")
                attr_type = str(raw_type) if isinstance(raw_type, str) else None
                sortable = _is_sortable(attr_type)
                attributes.append(
                    {
                        "name": str(name),
                        "displayName": meta.get("displayName", name),
                        "help": meta.get("help"),
                        "type": attr_type,
                        "isDisplayable": meta.get("isDisplayable", True),
                        "isSortable": sortable,
                        "isSuggested": sortable and _is_suggested_score(str(name)),
                    }
                )
    elif isinstance(attrs_raw, list):
        for meta in attrs_raw:
            if isinstance(meta, dict):
                attr_name = str(meta.get("name", ""))
                raw_type = meta.get("type")
                attr_type = str(raw_type) if isinstance(raw_type, str) else None
                sortable = _is_sortable(attr_type)
                attributes.append(
                    {
                        "name": attr_name,
                        "displayName": meta.get("displayName", attr_name),
                        "help": meta.get("help"),
                        "type": attr_type,
                        "isDisplayable": meta.get("isDisplayable", True),
                        "isSortable": sortable,
                        "isSuggested": sortable and _is_suggested_score(attr_name),
                    }
                )

    return {
        "attributes": cast(JSONValue, attributes),
        "recordType": exp.config.record_type,
    }


@router.get("/{experiment_id}/results/sortable-attributes")
async def get_sortable_attributes(experiment_id: str) -> JSONObject:
    """Return only sortable (numeric) attributes, with suggestions for known score columns."""
    full = await get_experiment_attributes(experiment_id)
    all_attrs = full.get("attributes", [])
    sortable = [
        a
        for a in (all_attrs if isinstance(all_attrs, list) else [])
        if isinstance(a, dict) and a.get("isSortable")
    ]
    return {
        "sortableAttributes": cast(JSONValue, sortable),
        "recordType": full.get("recordType"),
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
    exp = await store.aget(experiment_id)
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
    exp = await store.aget(experiment_id)
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
    exp = await store.aget(experiment_id)
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
    exp = await store.aget(experiment_id)
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
    exp = await store.aget(experiment_id)
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
    request: RunAnalysisRequest,
) -> JSONObject:
    """Create and run a WDK step analysis on the experiment's step."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    store = get_experiment_store()
    exp = await store.aget(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")
    if not exp.wdk_step_id:
        raise NotFoundError(title="No WDK strategy for this experiment")

    api = get_strategy_api(exp.config.site_id)
    result = await api.run_step_analysis(
        step_id=exp.wdk_step_id,
        analysis_type=request.analysis_name,
        parameters=request.parameters,
    )
    return result


@router.post("/{experiment_id}/refine")
async def refine_experiment(
    experiment_id: str,
    request: RefineRequest,
) -> JSONObject:
    """Add a step to the experiment's strategy (combine, transform, etc.)."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
    from veupath_chatbot.integrations.veupathdb.strategy_api import StepTreeNode

    store = get_experiment_store()
    exp = await store.aget(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")
    if not exp.wdk_strategy_id or not exp.wdk_step_id:
        raise NotFoundError(title="No WDK strategy for this experiment")

    api = get_strategy_api(exp.config.site_id)
    record_type = exp.config.record_type

    if request.action == "combine":
        new_step = await api.create_step(
            record_type=record_type,
            search_name=request.search_name,
            parameters=request.parameters,
            custom_name=f"Refinement: {request.search_name}",
        )
        new_step_id = new_step.get("id") if isinstance(new_step, dict) else None
        if not isinstance(new_step_id, int):
            raise NotFoundError(title="Failed to create new step")

        combined = await api.create_combined_step(
            primary_step_id=exp.wdk_step_id,
            secondary_step_id=new_step_id,
            boolean_operator=request.operator,
            record_type=record_type,
            custom_name=f"{request.operator} refinement",
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

    elif request.action == "transform":
        new_step = await api.create_transform_step(
            input_step_id=exp.wdk_step_id,
            transform_name=request.transform_name,
            parameters=request.parameters,
            record_type=record_type,
            custom_name=f"Transform: {request.transform_name}",
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

    return {"success": False, "error": f"Unknown action: {request.action}"}
