"""Results endpoints: records, record detail, attributes, strategy, distributions, analyses, refine."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter

from veupath_chatbot.platform.errors import (
    InternalError,
    NotFoundError,
    ValidationError,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.wdk.helpers import extract_pk
from veupath_chatbot.services.wdk.step_results import StepResultsService
from veupath_chatbot.transport.http.deps import CurrentUser, ExperimentDep
from veupath_chatbot.transport.http.schemas.experiments import (
    RefineRequest,
    RunAnalysisRequest,
)

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _require_step(exp: ExperimentDep) -> StepResultsService:
    """Create a StepResultsService, raising 404 if no WDK step."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    if not exp.wdk_step_id:
        raise NotFoundError(title="No WDK strategy for this experiment")
    api = get_strategy_api(exp.config.site_id)
    return StepResultsService(
        api, step_id=exp.wdk_step_id, record_type=exp.config.record_type
    )


@router.get("/{experiment_id}/results/attributes")
async def get_experiment_attributes(
    exp: ExperimentDep, user_id: CurrentUser
) -> JSONObject:
    """Get available attributes for an experiment's record type."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    api = get_strategy_api(exp.config.site_id)
    svc = StepResultsService(
        api, step_id=exp.wdk_step_id or 0, record_type=exp.config.record_type
    )
    return await svc.get_attributes()


@router.get("/{experiment_id}/results/sortable-attributes")
async def get_sortable_attributes(
    exp: ExperimentDep, user_id: CurrentUser
) -> JSONObject:
    """Return only sortable (numeric) attributes, with suggestions for known score columns."""
    full = await get_experiment_attributes(exp, user_id)
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
    exp: ExperimentDep,
    user_id: CurrentUser,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    dir: str = "ASC",
    attributes: str | None = None,
) -> JSONObject:
    """Get paginated result records for an experiment.

    Requires a persisted WDK strategy (``wdkStepId`` must be set).
    """
    if not exp.wdk_step_id or not exp.wdk_strategy_id:
        raise NotFoundError(
            title="No WDK strategy",
            detail="This experiment has no persisted WDK strategy for result browsing.",
        )

    svc = _require_step(exp)
    attr_list: list[str] | None = None
    if attributes:
        attr_list = [a.strip() for a in attributes.split(",") if a.strip()]

    answer = await svc.get_records(
        offset=offset,
        limit=limit,
        sort=sort,
        direction=dir,
        attributes=attr_list,
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
            gene_id = extract_pk(rec)
            classification: str | None = None
            if gene_id:
                # WDK transcript IDs include a version suffix (e.g. ".1").
                # Experiment gene sets store the base gene ID without it.
                candidates = [gene_id]
                dot = gene_id.rfind(".")
                if dot > 0:
                    candidates.append(gene_id[:dot])
                for gid in candidates:
                    if gid in tp_ids:
                        classification = "TP"
                        break
                    if gid in fp_ids:
                        classification = "FP"
                        break
                    if gid in fn_ids:
                        classification = "FN"
                        break
                    if gid in tn_ids:
                        classification = "TN"
                        break
            classified_records.append({**rec, "_classification": classification})

    return {
        "records": cast(JSONValue, classified_records),
        "meta": answer.get("meta", {}),
    }


@router.post("/{experiment_id}/results/record")
async def get_experiment_record_detail(
    exp: ExperimentDep,
    request_body: dict[str, object],
    user_id: CurrentUser,
) -> JSONObject:
    """Get a single record's full details by primary key."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    raw_pk = request_body.get("primaryKey") or request_body.get("primary_key") or []
    if not isinstance(raw_pk, list) or not raw_pk:
        raise ValidationError(title="Invalid primary key: must be a non-empty array")

    pk_parts: list[JSONObject] = [
        {"name": str(part.get("name", "")), "value": str(part.get("value", ""))}
        for part in raw_pk
        if isinstance(part, dict)
    ]

    api = get_strategy_api(exp.config.site_id)
    svc = StepResultsService(
        api, step_id=exp.wdk_step_id or 0, record_type=exp.config.record_type
    )
    return await svc.get_record_detail(pk_parts, exp.config.site_id)


@router.get("/{experiment_id}/strategy")
async def get_experiment_strategy(
    exp: ExperimentDep, user_id: CurrentUser
) -> JSONObject:
    """Get the WDK strategy tree for an experiment."""
    if not exp.wdk_strategy_id:
        raise NotFoundError(
            title="No WDK strategy",
            detail="This experiment has no persisted WDK strategy.",
        )
    svc = _require_step(exp)
    return await svc.get_strategy(exp.wdk_strategy_id)


@router.get("/{experiment_id}/results/distributions/{attribute_name}")
async def get_experiment_distribution(
    exp: ExperimentDep,
    attribute_name: str,
    user_id: CurrentUser,
) -> JSONObject:
    """Get distribution data for an attribute using the byValue column reporter."""
    svc = _require_step(exp)
    return await svc.get_distribution(attribute_name)


@router.get("/{experiment_id}/analyses/types")
async def get_experiment_analysis_types(
    exp: ExperimentDep, user_id: CurrentUser
) -> JSONObject:
    """List available WDK step analysis types for an experiment."""
    svc = _require_step(exp)
    return await svc.list_analysis_types()


@router.post("/{experiment_id}/analyses/run")
async def run_experiment_analysis(
    exp: ExperimentDep,
    request: RunAnalysisRequest,
    user_id: CurrentUser,
) -> JSONObject:
    """Create and run a WDK step analysis on the experiment's step.

    Uses the shared service for defaults+merge+run, but adds
    experiment-specific enrichment persistence.
    """
    from veupath_chatbot.services.experiment.enrichment import (
        is_enrichment_analysis,
        parse_enrichment_from_raw,
        upsert_enrichment_result,
    )
    from veupath_chatbot.services.experiment.types import to_json

    svc = _require_step(exp)
    raw_result, merged_params = await svc.run_analysis_raw(
        request.analysis_name, dict(request.parameters)
    )

    if is_enrichment_analysis(request.analysis_name):
        er = parse_enrichment_from_raw(request.analysis_name, merged_params, raw_result)
        upsert_enrichment_result(exp.enrichment_results, er)
        get_experiment_store().save(exp)
        return {
            "_resultType": "enrichment",
            "enrichmentResults": [to_json(er)],
        }

    return raw_result


@router.post("/{experiment_id}/refine")
async def refine_experiment(
    exp: ExperimentDep,
    request: RefineRequest,
    user_id: CurrentUser,
) -> JSONObject:
    """Add a step to the experiment's strategy (combine, transform, etc.)."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
    from veupath_chatbot.integrations.veupathdb.strategy_api import StepTreeNode

    if not exp.wdk_strategy_id or not exp.wdk_step_id:
        raise NotFoundError(title="No WDK strategy for this experiment")

    api = get_strategy_api(exp.config.site_id)
    record_type = exp.config.record_type
    store = get_experiment_store()

    if request.action == "combine":
        new_step = await api.create_step(
            record_type=record_type,
            search_name=request.search_name,
            parameters=request.parameters,
            custom_name=f"Refinement: {request.search_name}",
        )
        new_step_id = new_step.get("id") if isinstance(new_step, dict) else None
        if not isinstance(new_step_id, int):
            raise InternalError(title="Failed to create new step")

        combined = await api.create_combined_step(
            primary_step_id=exp.wdk_step_id,
            secondary_step_id=new_step_id,
            boolean_operator=request.operator,
            record_type=record_type,
            custom_name=f"{request.operator} refinement",
        )
        combined_id = combined.get("id") if isinstance(combined, dict) else None
        if not isinstance(combined_id, int):
            raise InternalError(title="Failed to create combined step")

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
            raise InternalError(title="Failed to create transform step")

        new_tree = StepTreeNode(
            new_step_id,
            primary_input=StepTreeNode(exp.wdk_step_id),
        )
        await api.update_strategy(exp.wdk_strategy_id, step_tree=new_tree)
        exp.wdk_step_id = new_step_id
        store.save(exp)

        return {"success": True, "newStepId": new_step_id}

    raise ValidationError(
        title=f"Unknown refine action: {request.action}",
        errors=[
            {
                "path": "action",
                "message": f"Unknown action: {request.action}",
                "code": "INVALID_ACTION",
            }
        ],
    )
