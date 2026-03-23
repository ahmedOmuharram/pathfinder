"""Results endpoints: records, record detail, attributes, distributions, refine."""

from dataclasses import dataclass
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Query

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKSearchConfig,
    WDKStepTree,
)
from veupath_chatbot.platform.errors import (
    NotFoundError,
    ValidationError,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.classification import classify_records
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.wdk import get_strategy_api
from veupath_chatbot.services.wdk.step_results import StepResultsService
from veupath_chatbot.transport.http.deps import CurrentUser, ExperimentDep
from veupath_chatbot.transport.http.schemas.experiments import RefineRequest
from veupath_chatbot.transport.http.schemas.steps import RecordDetailRequest

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Query parameter groups
# ---------------------------------------------------------------------------


@dataclass
class RecordQueryParams:
    """Grouped query parameters for record listing endpoints."""

    offset: int = Query(0, ge=0)
    limit: int = Query(50, ge=1, le=500)
    sort: str | None = None
    sort_dir: Literal["ASC", "DESC"] = Query("ASC", alias="dir")
    attributes: str | None = None
    filter_attribute: str | None = Query(None, alias="filterAttribute")
    filter_value: str | None = Query(None, alias="filterValue")


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _require_step(exp: ExperimentDep) -> StepResultsService:
    """Create a StepResultsService, raising 404 if no WDK step."""
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
    api = get_strategy_api(exp.config.site_id)
    svc = StepResultsService(
        api, step_id=exp.wdk_step_id or 0, record_type=exp.config.record_type
    )
    return await svc.get_attributes()


@router.get("/{experiment_id}/results/records")
async def get_experiment_records(
    exp: ExperimentDep,
    user_id: CurrentUser,
    params: Annotated[RecordQueryParams, Depends()],
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
    if params.attributes:
        attr_list = [a.strip() for a in params.attributes.split(",") if a.strip()]

    if params.filter_attribute and params.filter_value is not None:
        answer = await svc.get_records(
            offset=0,
            limit=10_000,
            sort=params.sort,
            direction=params.sort_dir,
            attributes=attr_list,
        )
        filtered_records = [
            rec
            for rec in answer.records
            if rec.attributes.get(params.filter_attribute) == params.filter_value
        ]
        classified = classify_records(
            filtered_records,
            tp_ids={g.id for g in exp.true_positive_genes},
            fp_ids={g.id for g in exp.false_positive_genes},
            fn_ids={g.id for g in exp.false_negative_genes},
            tn_ids={g.id for g in exp.true_negative_genes},
        )
        page = classified[params.offset : params.offset + params.limit]
        return {
            "records": cast("JSONValue", page),
            "meta": {
                "totalCount": len(classified),
                "displayTotalCount": len(classified),
                "responseCount": len(page),
                "pagination": {"offset": params.offset, "numRecords": params.limit},
                "attributes": cast("JSONValue", attr_list or []),
                "tables": cast("JSONValue", []),
            },
        }

    answer = await svc.get_records(
        offset=params.offset,
        limit=params.limit,
        sort=params.sort,
        direction=params.sort_dir,
        attributes=attr_list,
    )
    classified = classify_records(
        answer.records,
        tp_ids={g.id for g in exp.true_positive_genes},
        fp_ids={g.id for g in exp.false_positive_genes},
        fn_ids={g.id for g in exp.false_negative_genes},
        tn_ids={g.id for g in exp.true_negative_genes},
    )

    return {
        "records": cast("JSONValue", classified),
        "meta": answer.meta.model_dump(by_alias=True),
    }


@router.post("/{experiment_id}/results/record")
async def get_experiment_record_detail(
    exp: ExperimentDep,
    body: RecordDetailRequest,
    user_id: CurrentUser,
) -> JSONObject:
    """Get a single record's full details by primary key."""
    pk_parts: list[dict[str, str]] = [
        {"name": part.name, "value": part.value} for part in body.primary_key
    ]

    api = get_strategy_api(exp.config.site_id)
    svc = StepResultsService(
        api, step_id=exp.wdk_step_id or 0, record_type=exp.config.record_type
    )
    return await svc.get_record_detail(pk_parts, exp.config.site_id)


@router.get("/{experiment_id}/results/distributions/{attribute_name}")
async def get_experiment_distribution(
    exp: ExperimentDep,
    attribute_name: str,
    user_id: CurrentUser,
) -> JSONObject:
    """Get distribution data for an attribute using the byValue column reporter."""
    svc = _require_step(exp)
    dist = await svc.get_distribution(attribute_name)
    return dist.model_dump(by_alias=True)


@router.post("/{experiment_id}/refine")
async def refine_experiment(
    exp: ExperimentDep,
    request: RefineRequest,
    user_id: CurrentUser,
) -> JSONObject:
    """Add a step to the experiment's strategy (combine, transform, etc.)."""
    if not exp.wdk_strategy_id or not exp.wdk_step_id:
        raise NotFoundError(title="No WDK strategy for this experiment")

    api = get_strategy_api(exp.config.site_id)
    record_type = exp.config.record_type
    store = get_experiment_store()

    if request.action == "combine":
        new_step = await api.create_step(
            NewStepSpec(
                search_name=request.search_name,
                search_config=WDKSearchConfig(
                    parameters={k: str(v) for k, v in request.parameters.items() if v is not None},
                ),
                custom_name=f"Refinement: {request.search_name}",
            ),
            record_type=record_type,
        )
        new_step_id = new_step.id

        combined = await api.create_combined_step(
            primary_step_id=exp.wdk_step_id,
            secondary_step_id=new_step_id,
            boolean_operator=request.operator,
            record_type=record_type,
            spec_overrides=PatchStepSpec(custom_name=f"{request.operator} refinement"),
        )
        combined_id = combined.id

        new_tree = WDKStepTree(
            step_id=combined_id,
            primary_input=WDKStepTree(step_id=exp.wdk_step_id),
            secondary_input=WDKStepTree(step_id=new_step_id),
        )
        await api.update_strategy(exp.wdk_strategy_id, step_tree=new_tree)
        exp.wdk_step_id = combined_id
        store.save(exp)

        return {"success": True, "newStepId": combined_id}

    if request.action == "transform":
        new_step = await api.create_transform_step(
            NewStepSpec(
                search_name=request.transform_name,
                search_config=WDKSearchConfig(
                    parameters={k: str(v) for k, v in request.parameters.items() if v is not None},
                ),
                custom_name=f"Transform: {request.transform_name}",
            ),
            input_step_id=exp.wdk_step_id,
            record_type=record_type,
        )
        new_step_id = new_step.id

        new_tree = WDKStepTree(
            step_id=new_step_id,
            primary_input=WDKStepTree(step_id=exp.wdk_step_id),
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
