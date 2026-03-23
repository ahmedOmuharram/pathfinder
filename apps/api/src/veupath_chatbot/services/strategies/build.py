"""Strategy build service: compile, create/update, and count extraction.

Encapsulates all business logic for building a strategy on WDK. The AI tool
layer delegates to this module and only handles argument parsing and response
formatting.
"""

from dataclasses import dataclass
from typing import Protocol

from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.domain.strategy.compile import (
    CompilationResult,
    StepDecoratorAPI,
    StrategyCompilerAPI,
    apply_step_decorations,
    compile_strategy,
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
from veupath_chatbot.services.catalog.searches import (
    make_record_type_resolver,
    resolve_record_type_from_steps,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Protocols — I/O boundaries the build service depends on
# ---------------------------------------------------------------------------


class StrategyBuildAPI(StrategyCompilerAPI, StepDecoratorAPI, Protocol):
    """Combined protocol: compile steps + decorate + strategy CRUD.

    This is satisfied by the real ``StrategyAPI`` from the integrations layer.
    """

    async def create_strategy(
        self,
        step_tree: WDKStepTree,
        name: str,
        description: str | None = None,
    ) -> WDKIdentifier: ...

    async def update_strategy(
        self,
        strategy_id: int,
        step_tree: WDKStepTree | None = None,
        name: str | None = None,
    ) -> WDKStrategyDetails: ...

    async def get_strategy(self, strategy_id: int) -> WDKStrategyDetails: ...

    async def get_step_count(self, step_id: int) -> int: ...


class SiteInfoLike(Protocol):
    """Protocol for site metadata needed by the build service."""

    def strategy_url(
        self, strategy_id: int, root_step_id: int | None = None
    ) -> str: ...


# ---------------------------------------------------------------------------
# Factory helpers — resolve integrations so tool layer doesn't import them
# ---------------------------------------------------------------------------


def _get_build_api(site_id: str) -> StrategyBuildAPI:
    """Get a StrategyBuildAPI for the given site (delegates to integrations)."""
    return get_strategy_api(site_id)


def _get_site_info(site_id: str) -> SiteInfoLike:
    """Get site info for the given site (delegates to integrations)."""
    return get_site(site_id)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class BuildOptions:
    """Optional overrides for :func:`build_strategy`.

    Bundles the optional build controls so the signature stays within the
    six-argument limit.
    """

    root_step_id: str | None = None
    strategy_name: str | None = None
    description: str | None = None


@dataclass
class BuildResult:
    """Outcome of a successful strategy build."""

    wdk_strategy_id: int | None
    wdk_url: str | None
    root_step_id: int
    root_count: int | None
    step_count: int
    counts: dict[str, int | None]
    zero_step_ids: list[str]
    compilation: CompilationResult


@dataclass
class StepCountResult:
    """Outcome of a step count lookup."""

    step_id: int
    count: int


# ---------------------------------------------------------------------------
# Root resolution
# ---------------------------------------------------------------------------


class RootResolutionError(Exception):
    """Raised when a single root step cannot be resolved from the graph."""

    def __init__(self, message: str, root_count: int = 0) -> None:
        super().__init__(message)
        self.root_count = root_count


def resolve_root_step(
    graph: StrategyGraph,
    explicit_root_step_id: str | None,
) -> PlanStepNode:
    """Resolve the root step from the graph.

    :param graph: Strategy graph.
    :param explicit_root_step_id: Optional explicit root step ID override.
    :returns: The resolved root PlanStepNode.
    :raises RootResolutionError: When root cannot be determined.
    """

    if explicit_root_step_id:
        step = graph.get_step(explicit_root_step_id)
        if step:
            return step
        msg = f"Explicit root step '{explicit_root_step_id}' not found in graph."
        raise RootResolutionError(msg)

    if len(graph.roots) == 1:
        step = graph.get_step(next(iter(graph.roots)))
        if step:
            return step

    if len(graph.roots) > 1:
        msg = (
            f"Graph has {len(graph.roots)} subtree roots -- expected exactly 1 to build. "
            "Combine them first, or specify root_step_id."
        )
        raise RootResolutionError(
            msg,
            root_count=len(graph.roots),
        )

    msg = "No steps in graph. Create steps before building."
    raise RootResolutionError(msg)


# ---------------------------------------------------------------------------
# Strategy AST creation
# ---------------------------------------------------------------------------


def create_strategy_ast(
    graph: StrategyGraph,
    root_step: object,
    strategy_name: str | None,
    description: str | None,
) -> StrategyAST:
    """Create and validate a StrategyAST from graph state.

    Record type is read from ``graph.record_type`` which must already be
    set (either from step creation or auto-resolution in :func:`build_strategy`).

    :param graph: Strategy graph.
    :param root_step: Root PlanStepNode.
    :param strategy_name: Optional strategy name.
    :param description: Optional description.
    :returns: Validated StrategyAST.
    :raises ValueError: When record type is not set or validation fails.
    """
    if not isinstance(root_step, PlanStepNode):
        msg = f"Expected PlanStepNode, got {type(root_step).__name__}"
        raise StrategyCompilationError(msg)

    if not graph.record_type:
        msg = "Record type could not be inferred for execution."
        raise StrategyCompilationError(msg)

    strategy = StrategyAST(
        record_type=graph.record_type,
        root=root_step,
        name=strategy_name or graph.name,
        description=description,
    )
    validation_result = validate_strategy(strategy)
    if not validation_result.valid:
        errors = [
            {"path": e.path, "message": e.message} for e in validation_result.errors
        ]
        msg = f"Strategy validation failed: {errors}"
        raise StrategyCompilationError(msg)

    return strategy


# ---------------------------------------------------------------------------
# WDK create-or-update
# ---------------------------------------------------------------------------


async def create_or_update_wdk_strategy(
    api: StrategyBuildAPI,
    compilation_result: CompilationResult,
    strategy: StrategyAST,
    existing_wdk_id: int | None,
) -> int | None:
    """Create a new WDK strategy or update an existing one.

    If ``existing_wdk_id`` is provided, attempts to update first. Falls back to
    creating a new strategy if the update fails (e.g. 404 from WDK).

    :returns: The WDK strategy ID, or None if creation failed.
    """
    wdk_strategy_id: int | None = None

    if existing_wdk_id is not None:
        try:
            await api.update_strategy(
                strategy_id=existing_wdk_id,
                step_tree=compilation_result.step_tree,
                name=strategy.name or "Untitled Strategy",
            )
            wdk_strategy_id = existing_wdk_id
            logger.info(
                "Updated existing WDK strategy",
                wdk_strategy_id=existing_wdk_id,
            )
        except AppError as update_err:
            logger.warning(
                "Failed to update WDK strategy, will create new",
                wdk_strategy_id=existing_wdk_id,
                error=str(update_err),
            )
            wdk_strategy_id = None

    if wdk_strategy_id is None:
        wdk_result = await api.create_strategy(
            step_tree=compilation_result.step_tree,
            name=strategy.name or "Untitled Strategy",
            description=strategy.description,
        )
        wdk_strategy_id = wdk_result.id

    return wdk_strategy_id


# ---------------------------------------------------------------------------
# Step counts extraction
# ---------------------------------------------------------------------------


def extract_step_counts(
    strategy_info: WDKStrategyDetails,
    compiled_map: dict[str, int],
) -> tuple[dict[str, int | None], int | None]:
    """Extract per-step result counts from a WDK strategy payload.

    :param strategy_info: Typed WDK strategy details (from ``api.get_strategy``).
    :param compiled_map: Mapping of local_step_id -> wdk_step_id.
    :returns: Tuple of (step_counts dict, root_count).
    """
    step_counts: dict[str, int | None] = {}
    root_count: int | None = None

    wdk_to_local = {v: k for k, v in compiled_map.items()}

    for wdk_id_str, step in strategy_info.steps.items():
        try:
            wdk_id_int = int(wdk_id_str)
        except ValueError, TypeError:
            continue
        local_id = wdk_to_local.get(wdk_id_int)
        if local_id:
            step_counts[local_id] = step.estimated_size

    root_local = wdk_to_local.get(strategy_info.root_step_id)
    if root_local:
        root_count = step_counts.get(root_local)

    return step_counts, root_count


# ---------------------------------------------------------------------------
# Full build orchestration
# ---------------------------------------------------------------------------


async def build_strategy(
    *,
    graph: StrategyGraph,
    api: StrategyBuildAPI,
    site: SiteInfoLike,
    site_id: str,
    options: BuildOptions | None = None,
) -> BuildResult:
    """Build or update a strategy on WDK.

    Orchestrates: root resolution, AST creation, WDK compilation,
    create-or-update, step decorations, count extraction, and
    graph state mutation.

    Record type is auto-resolved from leaf searches via the pre-cached
    SearchCatalog — callers never need to supply it.

    :param options: Optional build overrides (root step, name, description).
    :raises RootResolutionError: If root step cannot be determined.
    :raises ValueError: If validation or record type inference fails.
    :raises Exception: On WDK API failures.
    """
    opts = options or BuildOptions()
    root_step_id = opts.root_step_id
    strategy_name = opts.strategy_name
    description = opts.description

    strategy = graph.current_strategy

    root_step = resolve_root_step(graph, root_step_id)

    # Create resolver upfront for both auto-resolution and compilation.
    resolver = await make_record_type_resolver(site_id)

    # Auto-resolve record type from leaf searches if not set on graph.
    if not graph.record_type:
        graph.record_type = await resolve_record_type_from_steps(root_step, resolver)

    needs_rebuild = root_step is not None and (
        not strategy
        or (root_step.id is not None and strategy.get_step_by_id(root_step.id) is None)
    )

    if not strategy or needs_rebuild:
        strategy = create_strategy_ast(graph, root_step, strategy_name, description)
        graph.current_strategy = strategy
        graph.save_history(f"Created strategy: {strategy_name or 'Untitled Strategy'}")

    if strategy_name:
        strategy.name = strategy_name
        graph.name = strategy_name

    logger.info("Building strategy", name=strategy.name)
    compilation_result = await compile_strategy(
        strategy, api, site_id=site_id, resolve_search_record_type=resolver
    )

    wdk_strategy_id = await create_or_update_wdk_strategy(
        api, compilation_result, strategy, graph.wdk_strategy_id
    )

    compiled_map = {s.local_id: s.wdk_step_id for s in compilation_result.steps}
    await apply_step_decorations(strategy, compiled_map, api)

    wdk_url = (
        site.strategy_url(wdk_strategy_id, compilation_result.root_step_id)
        if wdk_strategy_id
        else None
    )

    # Mutate graph state with build results.
    graph.wdk_step_ids = dict(compiled_map)
    graph.wdk_strategy_id = wdk_strategy_id

    # Fetch step counts and validations from WDK.
    step_counts: dict[str, int | None] = {}
    step_validations: dict[str, WDKValidation] = {}
    root_count: int | None = None
    if wdk_strategy_id is not None:
        try:
            strategy_info = await api.get_strategy(wdk_strategy_id)
            step_counts, root_count = extract_step_counts(
                strategy_info, compiled_map
            )
            for local_id, wdk_id in compiled_map.items():
                wdk_step = strategy_info.steps.get(str(wdk_id))
                if wdk_step is not None:
                    step_validations[local_id] = wdk_step.validation
        except AppError as e:
            logger.warning("Strategy count lookup failed", error=str(e))

    graph.step_counts = step_counts
    graph.step_validations = step_validations

    zeros = sorted([sid for sid, c in step_counts.items() if c == 0])

    return BuildResult(
        wdk_strategy_id=wdk_strategy_id,
        wdk_url=wdk_url,
        root_step_id=compilation_result.root_step_id,
        root_count=root_count,
        step_count=len(compilation_result.steps),
        counts=step_counts,
        zero_step_ids=zeros,
        compilation=compilation_result,
    )


# ---------------------------------------------------------------------------
# Result count lookup
# ---------------------------------------------------------------------------


async def get_estimated_size(
    api: StrategyBuildAPI,
    wdk_step_id: int,
    wdk_strategy_id: int | None = None,
) -> StepCountResult:
    """Get the result count for a built WDK step.

    First tries to read ``estimatedSize`` from the strategy payload (cheaper),
    then falls back to a direct step count query.

    :raises TypeError: If strategy payload is malformed.
    :raises Exception: On WDK API errors (propagated to caller).
    """
    if wdk_strategy_id is not None:
        strategy = await api.get_strategy(wdk_strategy_id)
        step = strategy.steps.get(str(wdk_step_id))
        if step is not None and step.estimated_size is not None:
            return StepCountResult(step_id=wdk_step_id, count=step.estimated_size)

    count = await api.get_step_count(wdk_step_id)
    return StepCountResult(step_id=wdk_step_id, count=count)


# ---------------------------------------------------------------------------
# Convenience entry points (resolve integrations internally)
# ---------------------------------------------------------------------------


async def build_strategy_for_site(
    *,
    graph: StrategyGraph,
    site_id: str,
    root_step_id: str | None = None,
    strategy_name: str | None = None,
    description: str | None = None,
) -> BuildResult:
    """Build a strategy using factory-resolved API and site info.

    This is the entry point for the AI tool layer -- it resolves the
    integration objects internally so callers don't import from integrations.
    """
    api = _get_build_api(site_id)
    site = _get_site_info(site_id)
    return await build_strategy(
        graph=graph,
        api=api,
        site=site,
        site_id=site_id,
        options=BuildOptions(
            root_step_id=root_step_id,
            strategy_name=strategy_name,
            description=description,
        ),
    )


async def get_estimated_size_for_site(
    site_id: str,
    wdk_step_id: int,
    wdk_strategy_id: int | None = None,
) -> StepCountResult:
    """Get result count using factory-resolved API.

    This is the entry point for the AI tool layer.
    """
    api = _get_build_api(site_id)
    return await get_estimated_size(api, wdk_step_id, wdk_strategy_id)
