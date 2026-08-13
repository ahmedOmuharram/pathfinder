"""Pushes local graph state to WDK: step tree, strategy, counts, decorations."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pydantic import JsonValue

from pathfinder.domain.strategy.ast import (
    StrategyStepNode,
    walk_step_tree,
)
from pathfinder.domain.strategy.graph_model import (
    pushable_root_id,
    rebuild_tree,
)
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.domain.strategy.validate import validate_strategy
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.veupathdb.factory import get_site, get_strategy_api
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKIdentifier,
    WDKStepTree,
    WDKStrategyDetails,
)
from pathfinder.platform.errors import AppError, StrategyCompilationError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject
from pathfinder.services.catalog.searches import (
    make_record_type_resolver,
    resolve_record_type_from_steps,
)
from pathfinder.services.strategies.build import RootResolutionError, resolve_root_step
from pathfinder.services.strategies.sync_state import WDKSyncState

logger = get_logger(__name__)


@runtime_checkable
class StepDecoratorAPI(Protocol):
    """I/O boundary for step decorations: filters, analyses, and reports."""

    async def set_step_filter(
        self,
        step_id: int,
        filter_name: str,
        value: JsonValue,
        *,
        disabled: bool = False,
    ) -> None: ...

    async def run_step_analysis(
        self,
        step_id: int,
        analysis_type: str,
        parameters: JSONObject | None = None,
        custom_name: str | None = None,
    ) -> JSONObject: ...

    async def run_step_report(
        self, step_id: int, report_name: str, config: JSONObject | None = None
    ) -> JsonValue: ...


class StrategySyncAPI(StepDecoratorAPI, Protocol):
    """I/O boundary for strategy sync operations."""

    async def create_strategy(
        self,
        step_tree: WDKStepTree,
        name: str,
        description: str | None = None,
        *,
        is_public: bool = False,
        is_saved: bool = False,
    ) -> WDKIdentifier: ...

    async def update_strategy(
        self,
        strategy_id: int,
        step_tree: WDKStepTree | None = None,
        name: str | None = None,
    ) -> WDKStrategyDetails: ...

    async def get_strategy(self, strategy_id: int) -> WDKStrategyDetails: ...


class SiteInfoLike(Protocol):
    """Site metadata that the sync service needs."""

    def strategy_url(
        self, strategy_id: int, root_step_id: int | None = None
    ) -> str: ...


@dataclass
class SyncResult:
    """Outcome of a successful strategy sync."""

    wdk_strategy_id: int | None
    wdk_url: str | None
    root_step_id: int
    counts: dict[str, int | None]
    root_count: int | None
    zero_step_ids: list[str]
    step_count: int


def build_step_tree_from_graph(
    root: StrategyStepNode,
    wdk_step_ids: dict[str, int],
) -> WDKStepTree:
    """Build a WDK step tree, replacing local step IDs with WDK step IDs.

    :raises StrategyCompilationError: If any step in the tree lacks a WDK step ID.
    """
    wdk_id = wdk_step_ids.get(root.id)
    if wdk_id is None:
        msg = f"Step '{root.id}' has no WDK step ID -- was it pushed to WDK?"
        raise StrategyCompilationError(msg)

    primary: WDKStepTree | None = None
    if root.primary_input is not None:
        primary = build_step_tree_from_graph(root.primary_input, wdk_step_ids)

    secondary: WDKStepTree | None = None
    if root.secondary_input is not None:
        secondary = build_step_tree_from_graph(root.secondary_input, wdk_step_ids)

    return WDKStepTree(
        step_id=wdk_id,
        primary_input=primary,
        secondary_input=secondary,
    )


def _trees_equal(a: WDKStepTree | None, b: WDKStepTree | None) -> bool:
    """Compare two step trees for structural equality."""
    if a is None or b is None:
        return a is b
    if a.step_id != b.step_id:
        return False
    return _trees_equal(a.primary_input, b.primary_input) and _trees_equal(
        a.secondary_input, b.secondary_input
    )


def _extract_counts_and_validations(
    strategy_info: WDKStrategyDetails,
    wdk_step_ids: dict[str, int],
) -> tuple[dict[str, int | None], dict[str, StepValidation], int | None]:
    """Extract per-step counts and validations, keyed by local step ID.

    :returns: Tuple of (counts, validations, root_count).
    """
    counts: dict[str, int | None] = {}
    validations: dict[str, StepValidation] = {}
    root_count: int | None = None

    wdk_to_local = {v: k for k, v in wdk_step_ids.items()}

    for wdk_id_str, wdk_step in strategy_info.steps.items():
        try:
            wdk_id = int(wdk_id_str)
        except ValueError, TypeError:
            continue
        local_id = wdk_to_local.get(wdk_id)
        if local_id:
            counts[local_id] = wdk_step.estimated_size
            validations[local_id] = wdk_step.validation

    root_local = wdk_to_local.get(strategy_info.root_step_id)
    if root_local:
        root_count = counts.get(root_local)

    return counts, validations, root_count


async def _apply_decorations(
    root_step: StrategyStepNode,
    wdk_step_ids: dict[str, int],
    api: StepDecoratorAPI,
) -> None:
    """Apply declared filters, analyses, and reports to each WDK step."""
    for step in walk_step_tree(root_step):
        wdk_step_id = wdk_step_ids.get(step.id)
        if wdk_step_id is None:
            continue
        for step_filter in step.filters:
            await api.set_step_filter(
                step_id=wdk_step_id,
                filter_name=step_filter.name,
                value=step_filter.value,
                disabled=step_filter.disabled,
            )
        for analysis in step.analyses:
            await api.run_step_analysis(
                step_id=wdk_step_id,
                analysis_type=analysis.analysis_type,
                parameters=analysis.parameters,
                custom_name=analysis.custom_name,
            )
        for report in step.reports:
            await api.run_step_report(
                step_id=wdk_step_id,
                report_name=report.report_name,
                config=report.config,
            )


async def _create_or_update_wdk_strategy(
    api: StrategySyncAPI,
    step_tree: WDKStepTree,
    name: str,
    sync_state: WDKSyncState,
) -> int:
    """Create a new WDK strategy, or update the existing one.

    A failed update creates a new strategy instead.

    :returns: The WDK strategy ID.
    """
    wdk_strategy_id = sync_state.wdk_strategy_id

    if wdk_strategy_id is None:
        result = await api.create_strategy(step_tree, name)
        logger.info("Created WDK strategy", wdk_strategy_id=result.id)
        return result.id

    if not _trees_equal(step_tree, sync_state.wdk_step_tree):
        try:
            await api.update_strategy(
                strategy_id=wdk_strategy_id,
                step_tree=step_tree,
                name=name,
            )
        except AppError as update_err:
            logger.warning(
                "Failed to update WDK strategy, creating new",
                wdk_strategy_id=wdk_strategy_id,
                error=str(update_err),
            )
            result = await api.create_strategy(step_tree, name)
            return result.id
        else:
            logger.info(
                "Updated WDK strategy step tree",
                wdk_strategy_id=wdk_strategy_id,
            )
            return wdk_strategy_id

    logger.debug(
        "Step tree unchanged, skipping WDK update",
        wdk_strategy_id=wdk_strategy_id,
    )
    return wdk_strategy_id


async def _fetch_strategy_state(
    api: StrategySyncAPI,
    wdk_strategy_id: int,
    wdk_step_ids: dict[str, int],
    step_tree: WDKStepTree,
) -> tuple[dict[str, int | None], dict[str, StepValidation], int | None, int]:
    """Fetch strategy details.

    :returns: Tuple of (counts, validations, root_count, root_wdk_step_id).
    """
    try:
        strategy_info = await api.get_strategy(wdk_strategy_id)
    except AppError as e:
        logger.warning("Strategy count lookup failed", error=str(e))
        return {}, {}, None, step_tree.step_id
    else:
        counts, validations, root_count = _extract_counts_and_validations(
            strategy_info, wdk_step_ids
        )
        return counts, validations, root_count, strategy_info.root_step_id


async def sync_strategy(
    *,
    graph: StrategyGraph,
    sync_state: WDKSyncState,
    api: StrategySyncAPI,
    site: SiteInfoLike,
    site_id: str,
    strategy_name: str | None = None,
) -> SyncResult:
    """Sync graph state to WDK: build step tree, create or update strategy, fetch counts.

    Every step must already hold a WDK step ID.

    :raises RootResolutionError: If root step cannot be determined.
    :raises StrategyCompilationError: If steps lack WDK IDs or validation fails.
    :raises AppError: On WDK API failures.
    """
    root = resolve_root_step(graph, None)
    # A combine step that lacks an input is not computable. WDK receives the
    # surviving branch instead.
    pushable_id = pushable_root_id(root.id, graph.steps)
    if pushable_id is None:
        msg = "No computable step in graph. Finish wiring the strategy first."
        raise RootResolutionError(msg)
    root_step = rebuild_tree(pushable_id, graph.steps)

    if not graph.record_type:
        resolver = await make_record_type_resolver(site_id)
        graph.record_type = await resolve_record_type_from_steps(root_step, resolver)

    _validate_graph(root_step, graph.record_type)

    step_tree = build_step_tree_from_graph(root_step, sync_state.wdk_step_ids)

    name = strategy_name or graph.name or "Untitled Strategy"
    wdk_strategy_id = await _create_or_update_wdk_strategy(
        api, step_tree, name, sync_state
    )

    counts, validations, root_count, root_wdk_step_id = await _fetch_strategy_state(
        api, wdk_strategy_id, sync_state.wdk_step_ids, step_tree
    )

    await _maybe_apply_decorations(root_step, sync_state.wdk_step_ids, api)

    sync_state.wdk_strategy_id = wdk_strategy_id
    sync_state.wdk_step_tree = step_tree
    sync_state.step_counts = counts
    sync_state.step_validations = validations

    all_steps = walk_step_tree(root_step)
    wdk_url = site.strategy_url(wdk_strategy_id, root_wdk_step_id)
    zeros = sorted([sid for sid, c in counts.items() if c == 0])

    return SyncResult(
        wdk_strategy_id=wdk_strategy_id,
        wdk_url=wdk_url,
        root_step_id=root_wdk_step_id,
        counts=counts,
        root_count=root_count,
        zero_step_ids=zeros,
        step_count=len(all_steps),
    )


def _validate_graph(root_step: StrategyStepNode, record_type: str | None) -> None:
    """Validate the strategy structure when a record type is known."""
    if not record_type:
        return
    validation_result = validate_strategy(root_step, record_type)
    if not validation_result.valid:
        errors = [
            {"path": e.path, "message": e.message} for e in validation_result.errors
        ]
        msg = f"Strategy validation failed: {errors}"
        raise StrategyCompilationError(msg)


async def _maybe_apply_decorations(
    root_step: StrategyStepNode,
    wdk_step_ids: dict[str, int],
    api: StepDecoratorAPI,
) -> None:
    """Apply step decorations when at least one step declares them."""
    all_steps = walk_step_tree(root_step)
    has_decorations = any(
        step.filters or step.analyses or step.reports for step in all_steps
    )
    if not has_decorations:
        return
    try:
        await _apply_decorations(root_step, wdk_step_ids, api)
    except AppError as e:
        logger.warning("Step decoration failed (non-fatal)", error=str(e))


async def sync_strategy_for_site(
    *,
    graph: StrategyGraph,
    sync_state: WDKSyncState,
    site_id: str,
    strategy_name: str | None = None,
) -> SyncResult:
    """Sync a strategy, resolving the API and site info from the site ID."""
    api = get_strategy_api(site_id)
    site = get_site(site_id)
    return await sync_strategy(
        graph=graph,
        sync_state=sync_state,
        api=api,
        site=site,
        site_id=site_id,
        strategy_name=strategy_name,
    )
