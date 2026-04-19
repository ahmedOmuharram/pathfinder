"""Results endpoints: records, record detail, attributes, distributions, refine."""

from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query
from pydantic import JsonValue

from pathfinder.platform.errors import (
    NotFoundError,
    ValidationError,
)
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject
from pathfinder.services.experiment.classification import classify_records
from pathfinder.services.experiment.refine import (
    apply_transform,
    combine_with_search,
)
from pathfinder.services.experiment.store import get_experiment_store
from pathfinder.services.wdk import (
    WDKSortDirection,
    encode_wdk_params,
    get_strategy_api,
)
from pathfinder.services.wdk.step_results import StepResultsService
from pathfinder.transport.http.deps import CurrentUser, ExperimentDep
from pathfinder.transport.http.schemas.experiments import RefineRequest, RefineResponse
from pathfinder.transport.http.schemas.step_results import (
    AttributesResponse,
    ClassifiedRecord,
    DistributionResponse,
    RecordDetailResponse,
    RecordsMeta,
    RecordsPagination,
    RecordsResponse,
)
from pathfinder.transport.http.schemas.steps import RecordDetailRequest

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
    sort_dir: Annotated[WDKSortDirection, Query(alias="dir")] = "ASC"
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

@router.get("/{experiment_id}/results/attributes", response_model=AttributesResponse)
async def get_experiment_attributes(
    exp: ExperimentDep, user_id: CurrentUser,
) -> AttributesResponse:
    """Get available attributes for an experiment's record type."""
    api = get_strategy_api(exp.config.site_id)
    svc = StepResultsService(
        api, step_id=exp.wdk_step_id or 0, record_type=exp.config.record_type,
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
            "records": cast("JsonValue", page),
            "meta": {
                "totalCount": len(classified),
                "displayTotalCount": len(classified),
                "responseCount": len(page),
                "pagination": {"offset": params.offset, "numRecords": params.limit},
                "attributes": cast("JsonValue", attr_list or []),
                "tables": cast("JsonValue", []),
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

    meta = answer.meta.model_dump(by_alias=True)
    meta["pagination"] = {"offset": params.offset, "numRecords": params.limit}
    return {
        "records": cast("JsonValue", classified),
        "meta": meta,
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

@router.post("/{experiment_id}/refine", response_model=RefineResponse)
async def refine_experiment(
    exp: ExperimentDep,
    request: RefineRequest,
    user_id: CurrentUser,
) -> RefineResponse:
    """Add a step to the experiment's strategy (combine, transform, etc.)."""
    api = get_strategy_api(exp.config.site_id)
    store = get_experiment_store()

    params = encode_wdk_params(request.parameters)

    if request.action == "combine":
        result = await combine_with_search(
            api=api,
            exp=exp,
            search_name=request.search_name,
            parameters=params,
            operator=request.operator,
            store=store,
        )
        return RefineResponse(success=True, new_step_id=result.new_step_id)

    if request.action == "transform":
        result = await apply_transform(
            api=api,
            exp=exp,
            transform_name=request.transform_name,
            parameters=params,
            store=store,
        )
        return RefineResponse(success=True, new_step_id=result.new_step_id)

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
