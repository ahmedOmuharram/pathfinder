"""WDK sync: fetch WDK strategies and sync into CQRS projections.

Handles:
- ``fetch_and_convert`` — fetch WDK strategy, convert to AST, normalize params
- ``sync_to_projection`` — full sync flow: fetch + upsert into CQRS
- ``upsert_projection`` — create-or-update a stream projection from WDK data
- ``upsert_summary_projection`` — create-or-update from list summary data
- ``plan_needs_detail_fetch`` — check if a projection needs WDK detail fetch
- ``lazy_fetch_wdk_detail`` — lazy-load full WDK detail for summary-only projections
- ``sync_is_saved_to_wdk`` — sync isSaved flag from projection to WDK
"""

from dataclasses import dataclass, field
from uuid import UUID

from veupath_chatbot.domain.strategy.ast import StrategyAST
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKStrategySummary
from veupath_chatbot.persistence.models import StreamProjection
from veupath_chatbot.persistence.repositories.stream import (
    ProjectionUpdate,
    StreamRepository,
)
from veupath_chatbot.platform.errors import AppError, InternalError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.wdk import get_strategy_api

from .wdk_conversion import (
    build_snapshot_from_wdk,
    normalize_synced_parameters,
)

logger = get_logger(__name__)


@dataclass
class WdkProjectionSpec:
    """Data needed to upsert a WDK strategy projection.

    Bundles the strategy-specific fields for :func:`upsert_projection` so the
    signature stays within the six-argument limit.
    """

    wdk_id: int
    name: str
    plan: JSONObject
    record_type: str | None
    is_saved: bool
    step_count: int = field(default=0)


def plan_needs_detail_fetch(projection: StreamProjection) -> bool:
    """Check if a WDK-linked projection needs its full detail fetched from WDK.

    Returns True when the projection has a ``wdk_strategy_id`` but no plan data
    (i.e. it was synced with summary data only and the user is now opening it).
    Local strategies (no ``wdk_strategy_id``) never need a WDK fetch.
    """
    if projection.wdk_strategy_id is None:
        return False
    plan = projection.plan
    if not isinstance(plan, dict) or not plan:
        return True
    return "root" not in plan


async def fetch_and_convert(
    api: StrategyAPI,
    wdk_id: int,
) -> tuple[StrategyAST, bool]:
    """Fetch a WDK strategy and convert to internal AST.

    Normalizes parameters best-effort (failures are logged and swallowed).
    Step counts and WDK step ID mappings are stored on the AST directly.

    :returns: Tuple of (StrategyAST, is_saved).
    """
    wdk_strategy = await api.get_strategy(wdk_id)

    ast = build_snapshot_from_wdk(wdk_strategy)

    try:
        await normalize_synced_parameters(ast, api)
    except AppError as exc:
        logger.warning(
            "Parameter normalization failed, storing raw values",
            wdk_id=wdk_id,
            error=str(exc),
        )

    return ast, wdk_strategy.is_saved


async def sync_to_projection(
    *,
    wdk_id: int,
    site_id: str,
    api: StrategyAPI,
    stream_repo: StreamRepository,
    user_id: UUID,
) -> StreamProjection:
    """Fetch a single WDK strategy and upsert into the CQRS layer.

    Shared by ``open_strategy`` and ``sync_all_wdk_strategies``.
    """
    ast, is_saved = await fetch_and_convert(api, wdk_id)
    plan = ast.model_dump(by_alias=True, exclude_none=True, mode="json")
    name = ast.name or f"WDK Strategy {wdk_id}"

    return await upsert_projection(
        stream_repo=stream_repo,
        user_id=user_id,
        site_id=site_id,
        spec=WdkProjectionSpec(
            wdk_id=wdk_id,
            name=name,
            plan=plan,
            record_type=ast.record_type,
            is_saved=is_saved,
            step_count=len(ast.get_all_steps()),
        ),
    )


async def upsert_projection(
    *,
    stream_repo: StreamRepository,
    user_id: UUID,
    site_id: str,
    spec: WdkProjectionSpec,
) -> StreamProjection:
    """Upsert a WDK strategy into the CQRS layer (create or update stream projection)."""
    existing = await stream_repo.get_by_wdk_strategy_id(user_id, spec.wdk_id)
    if existing:
        await stream_repo.update_projection(
            existing.stream_id,
            ProjectionUpdate(
                name=spec.name,
                plan=spec.plan,
                record_type=spec.record_type,
                wdk_strategy_id=spec.wdk_id,
                wdk_strategy_id_set=True,
                is_saved=spec.is_saved,
                is_saved_set=True,
                step_count=spec.step_count,
            ),
        )
        proj = await stream_repo.get_projection(existing.stream_id)
    else:
        stream = await stream_repo.create(
            user_id=user_id,
            site_id=site_id,
            name=spec.name,
        )
        await stream_repo.update_projection(
            stream.id,
            ProjectionUpdate(
                plan=spec.plan,
                record_type=spec.record_type,
                wdk_strategy_id=spec.wdk_id,
                wdk_strategy_id_set=True,
                is_saved=spec.is_saved,
                is_saved_set=True,
                step_count=spec.step_count,
            ),
        )
        proj = await stream_repo.get_projection(stream.id)

    if proj is None:
        msg = f"Projection disappeared for WDK strategy {spec.wdk_id}"
        raise InternalError(detail=msg)
    return proj


async def upsert_summary_projection(
    wdk_item: WDKStrategySummary,
    *,
    stream_repo: StreamRepository,
    user_id: UUID,
    site_id: str,
) -> StreamProjection | None:
    """Create or update a projection from WDK list summary data only.

    Unlike ``sync_to_projection``, this does NOT fetch the full strategy detail
    from WDK. It only stores metadata available from the list endpoint:
    name, recordClassName, estimatedSize, isSaved, leafAndTransformStepCount.

    The ``plan`` field is left untouched (empty for new projections, preserved
    for existing ones). Full plan data is fetched lazily on first GET.

    Returns the projection.
    """
    wdk_id = wdk_item.strategy_id
    name = wdk_item.name or f"WDK Strategy {wdk_id}"
    record_type = (
        wdk_item.record_class_name.strip()
        if wdk_item.record_class_name
        else None
    )
    is_saved = wdk_item.is_saved
    estimated_size = wdk_item.estimated_size
    step_count = wdk_item.leaf_and_transform_step_count

    existing = await stream_repo.get_by_wdk_strategy_id(user_id, wdk_id)
    if existing and existing.dismissed_at is not None:
        # Strategy was dismissed by user — don't re-import or update it.
        return existing
    if existing:
        await stream_repo.update_projection(
            existing.stream_id,
            ProjectionUpdate(
                name=name,
                record_type=record_type,
                wdk_strategy_id=wdk_id,
                wdk_strategy_id_set=True,
                is_saved=is_saved,
                is_saved_set=True,
                step_count=step_count,
                estimated_size=estimated_size,
                estimated_size_set=True,
            ),
        )
        proj = await stream_repo.get_projection(existing.stream_id)
    else:
        stream = await stream_repo.create(
            user_id=user_id,
            site_id=site_id,
            name=name,
        )
        await stream_repo.update_projection(
            stream.id,
            ProjectionUpdate(
                record_type=record_type,
                wdk_strategy_id=wdk_id,
                wdk_strategy_id_set=True,
                is_saved=is_saved,
                is_saved_set=True,
                step_count=step_count,
                estimated_size=estimated_size,
                estimated_size_set=True,
            ),
        )
        proj = await stream_repo.get_projection(stream.id)

    return proj


async def lazy_fetch_wdk_detail(
    *,
    projection: StreamProjection,
    stream_repo: StreamRepository,
) -> StreamProjection:
    """Fetch full WDK strategy detail for a summary-only projection.

    If the projection has a wdk_strategy_id but no plan data (created during
    sync-wdk to avoid N+1), fetches the full detail from WDK now and updates
    the projection. Returns the updated projection, or the original if no
    fetch was needed or the fetch failed.
    """
    site_id = projection.site_id
    wdk_id = projection.wdk_strategy_id
    if not plan_needs_detail_fetch(projection) or not site_id or wdk_id is None:
        return projection

    try:
        api = get_strategy_api(site_id)
        ast, is_saved = await fetch_and_convert(api, wdk_id)
        plan = ast.model_dump(by_alias=True, exclude_none=True, mode="json")
        await stream_repo.update_projection(
            projection.stream_id,
            ProjectionUpdate(
                plan=plan,
                record_type=ast.record_type,
                step_count=len(ast.get_all_steps()),
                is_saved=is_saved,
                is_saved_set=True,
            ),
        )
        updated = await stream_repo.get_projection(projection.stream_id)
        if updated is not None:
            return updated
    except (AppError, RuntimeError) as exc:
        logger.warning(
            "Lazy WDK detail fetch failed",
            stream_id=str(projection.stream_id),
            wdk_id=wdk_id,
            error=str(exc),
        )

    return projection


async def sync_is_saved_to_wdk(
    *,
    projection: StreamProjection,
) -> None:
    """Sync the isSaved flag from a projection to WDK.

    No-op if the projection has no wdk_strategy_id or site_id.
    Failures are logged and swallowed (non-critical sync).
    """
    wdk_id = projection.wdk_strategy_id
    if not wdk_id:
        return

    site_id = projection.stream.site_id if projection.stream else ""
    if not site_id:
        return

    try:
        api = get_strategy_api(site_id)
        await api.set_saved(wdk_id, is_saved=projection.is_saved)
    except AppError as exc:
        logger.warning(
            "Failed to sync isSaved to WDK",
            stream_id=str(projection.stream_id),
            wdk_id=wdk_id,
            error=str(exc),
        )
