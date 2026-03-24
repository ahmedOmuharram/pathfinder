"""Strategy sync service: push local graph state to WDK.

Lightweight replacement for the build pipeline. Builds a WDK step tree
from graph topology, creates or updates the WDK strategy, fetches counts,
and applies step decorations. Steps already have WDK IDs (from
creation-time push) -- the sync just manages the strategy and fetches
counts.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    walk_step_tree,
)
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.domain.strategy.validate import validate_strategy
from veupath_chatbot.integrations.veupathdb.factory import get_site, get_strategy_api
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKIdentifier,
    WDKStepTree,
    WDKStrategyDetails,
    WDKValidation,
)
from veupath_chatbot.platform.errors import AppError, StrategyCompilationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.catalog.searches import (
    make_record_type_resolver,
    resolve_record_type_from_steps,
)
from veupath_chatbot.services.strategies.build import resolve_root_step

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Protocols -- I/O boundaries the sync service depends on
# ---------------------------------------------------------------------------


@runtime_checkable
class StepDecoratorAPI(Protocol):
    """I/O boundary for post-compilation step decorations (filters, analyses, reports)."""

    async def set_step_filter(
        self,
        step_id: int,
        filter_name: str,
        value: JSONValue,
        *,
        disabled: bool = False,
    ) -> JSONValue: ...

    async def run_step_analysis(
        self,
        step_id: int,
        analysis_type: str,
        parameters: JSONObject | None = None,
        custom_name: str | None = None,
    ) -> JSONObject: ...

    async def run_step_report(
        self, step_id: int, report_name: str, config: JSONObject | None = None
    ) -> JSONValue: ...


class StrategySyncAPI(StepDecoratorAPI, Protocol):
    """I/O boundary for strategy sync operations.

    Satisfied by the real ``StrategyAPI`` from the integrations layer.
    """

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
    """Protocol for site metadata needed by the sync service."""

    def strategy_url(
        self, strategy_id: int, root_step_id: int | None = None
    ) -> str: ...


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Step tree construction
# ---------------------------------------------------------------------------


def build_step_tree_from_graph(
    root: PlanStepNode,
    wdk_step_ids: dict[str, int],
) -> WDKStepTree:
    """Build a WDKStepTree from graph topology and WDK step IDs.

    Recursively walks a ``PlanStepNode`` tree and replaces local step IDs
    with WDK step IDs.

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


# ---------------------------------------------------------------------------
# Tree comparison
# ---------------------------------------------------------------------------


def _trees_equal(a: WDKStepTree | None, b: WDKStepTree | None) -> bool:
    """Check structural equality of two WDKStepTree objects."""
    if a is None or b is None:
        return a is b
    if a.step_id != b.step_id:
        return False
    return _trees_equal(a.primary_input, b.primary_input) and _trees_equal(
        a.secondary_input, b.secondary_input
    )


# ---------------------------------------------------------------------------
# Count and validation extraction
# ---------------------------------------------------------------------------


def _extract_counts_and_validations(
    strategy_info: WDKStrategyDetails,
    wdk_step_ids: dict[str, int],
) -> tuple[dict[str, int | None], dict[str, WDKValidation], int | None]:
    """Extract per-step counts and validations from a WDK strategy payload.

    Maps WDK step IDs back to local step IDs and extracts ``estimatedSize``
    and ``validation`` for each step.

    :returns: Tuple of (counts, validations, root_count).
    """
    counts: dict[str, int | None] = {}
    validations: dict[str, WDKValidation] = {}
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


# ---------------------------------------------------------------------------
# Step decorations
# ---------------------------------------------------------------------------


async def _apply_decorations(
    root_step: PlanStepNode,
    wdk_step_ids: dict[str, int],
    api: StepDecoratorAPI,
) -> None:
    """Apply filters, analyses, and reports to compiled WDK steps.

    Walks the step tree directly and applies any declared decorations
    (filters, analyses, reports) to each step's WDK counterpart.
    """
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


# ---------------------------------------------------------------------------
# Create-or-update strategy on WDK
# ---------------------------------------------------------------------------


async def _create_or_update_wdk_strategy(
    api: StrategySyncAPI,
    step_tree: WDKStepTree,
    name: str,
    graph: StrategyGraph,
) -> int:
    """Create a new WDK strategy or update an existing one.

    Falls back to creating a new strategy if the update fails (e.g. 404).

    :returns: The WDK strategy ID.
    """
    wdk_strategy_id = graph.wdk_strategy_id

    if wdk_strategy_id is None:
        result = await api.create_strategy(step_tree, name)
        logger.info("Created WDK strategy", wdk_strategy_id=result.id)
        return result.id

    if not _trees_equal(step_tree, graph.wdk_step_tree):
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


# ---------------------------------------------------------------------------
# Fetch counts and apply decorations
# ---------------------------------------------------------------------------


async def _fetch_strategy_state(
    api: StrategySyncAPI,
    wdk_strategy_id: int,
    wdk_step_ids: dict[str, int],
    step_tree: WDKStepTree,
) -> tuple[dict[str, int | None], dict[str, WDKValidation], int | None, int]:
    """Fetch strategy details and extract counts, validations, and root step ID.

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


# ---------------------------------------------------------------------------
# Main sync function
# ---------------------------------------------------------------------------


async def sync_strategy(
    *,
    graph: StrategyGraph,
    api: StrategySyncAPI,
    site: SiteInfoLike,
    site_id: str,
    strategy_name: str | None = None,
) -> SyncResult:
    """Sync graph state to WDK: build step tree, create/update strategy, fetch counts.

    Steps must already have WDK IDs (from creation-time push). This function
    manages the strategy resource and fetches result counts.

    :raises RootResolutionError: If root step cannot be determined.
    :raises StrategyCompilationError: If steps lack WDK IDs or validation fails.
    :raises AppError: On WDK API failures.
    """
    # 1. Resolve root step from graph.
    root_step = resolve_root_step(graph, None)

    # 2. Auto-resolve record type from leaf searches if not set.
    if not graph.record_type:
        resolver = await make_record_type_resolver(site_id)
        graph.record_type = await resolve_record_type_from_steps(root_step, resolver)

    # 3. Validate strategy structure.
    _validate_graph(root_step, graph.record_type)

    # 4. Build step tree from graph topology + WDK step IDs.
    step_tree = build_step_tree_from_graph(root_step, graph.wdk_step_ids)

    # 5. Create or update WDK strategy.
    name = strategy_name or graph.name or "Untitled Strategy"
    wdk_strategy_id = await _create_or_update_wdk_strategy(api, step_tree, name, graph)

    # 6. Fetch strategy details for counts and validations.
    counts, validations, root_count, root_wdk_step_id = await _fetch_strategy_state(
        api, wdk_strategy_id, graph.wdk_step_ids, step_tree
    )

    # 7. Apply step decorations (filters, analyses, reports).
    await _maybe_apply_decorations(root_step, graph.wdk_step_ids, api)

    # 8. Update graph state.
    graph.wdk_strategy_id = wdk_strategy_id
    graph.wdk_step_tree = step_tree
    graph.step_counts = counts
    graph.step_validations = validations

    # 9. Build URL and return result.
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


def _validate_graph(root_step: PlanStepNode, record_type: str | None) -> None:
    """Validate the strategy structure if a record type is available."""
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
    root_step: PlanStepNode,
    wdk_step_ids: dict[str, int],
    api: StepDecoratorAPI,
) -> None:
    """Apply step decorations if any steps have filters, analyses, or reports."""
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


# ---------------------------------------------------------------------------
# Convenience entry point (resolves integrations internally)
# ---------------------------------------------------------------------------


async def sync_strategy_for_site(
    *,
    graph: StrategyGraph,
    site_id: str,
    strategy_name: str | None = None,
) -> SyncResult:
    """Sync a strategy using factory-resolved API and site info.

    This is the entry point for the AI tool layer -- it resolves the
    integration objects internally so callers don't import from integrations.
    """
    api = get_strategy_api(site_id)
    site = get_site(site_id)
    return await sync_strategy(
        graph=graph,
        api=api,
        site=site,
        site_id=site_id,
        strategy_name=strategy_name,
    )
