"""WDK -> plan conversion: parse typed WDK strategy models into internal plan.

Pure conversion functions (no I/O except ``canonicalize_synced_parameters``
which fetches param specs from WDK).

Public API:
- ``build_snapshot_from_wdk`` -- WDKStrategyDetails -> StrategyAst (with step_counts and wdk_step_ids)
- ``canonicalize_synced_parameters`` -- enrich plan nodes with canonicalized
  decoded param values (vocab-matched, leaf-enforced, native types)
"""

from pathfinder.domain.parameters.canonicalize import ParameterCanonicalizer
from pathfinder.domain.parameters.values import ParamKind, as_param_kind
from pathfinder.domain.strategy.ast import (
    StrategyStepNode,
    walk_step_tree,
)
from pathfinder.domain.strategy.ops import parse_op
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.integrations.veupathdb.strategy_api import StrategyAPI
from pathfinder.integrations.veupathdb.value_decoding import decode_params
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKSearch,
    WDKStep,
    WDKStepTree,
    WDKStrategyDetails,
)
from pathfinder.platform.errors import AppError, DataParsingError
from pathfinder.platform.logging import get_logger
from pathfinder.services.catalog.param_adapters import adapt_param_specs_from_search

logger = get_logger(__name__)


# -- Internal conversion helpers ------------------------------------------------


def _extract_operator(parameters: dict[str, str]) -> str | None:
    """Find the boolean operator in a combine step's parameter dict."""
    for key, value in parameters.items():
        if "operator" in key.lower():
            return value
    return None


def _resolve_expanded_reference(
    combine_step: WDKStep,
    secondary_node: StrategyStepNode,
    steps: dict[str, WDKStep],
) -> tuple[int | None, str | None]:
    """Map WDK ``expanded``/``expandedName`` onto the secondary input.

    WDK marks the *secondary input* of a combine as expanded when that
    branch was inserted from a saved strategy. We carry the saved
    strategy's id and label on our combine node so the UI can collapse
    the branch back to a "Insert saved strategy" pill.
    """
    if not combine_step.expanded:
        return (None, None)
    secondary_step_id = int(secondary_node.id) if secondary_node.id.isdigit() else None
    if secondary_step_id is None:
        return (None, None)
    secondary_wdk = steps.get(str(secondary_step_id))
    if secondary_wdk is None or secondary_wdk.strategy_id is None:
        return (None, None)
    return (secondary_wdk.strategy_id, combine_step.expanded_name)


def _build_node(
    tree_node: WDKStepTree,
    steps: dict[str, WDKStep],
    record_type: str,
    wire_by_step_id: dict[str, dict[str, str]],
) -> StrategyStepNode:
    """Recursively build a ``StrategyStepNode`` tree from typed WDK models.

    Parameter values are left empty here: WDK wire form lacks the param-spec
    context needed to type each value. The sidecar ``wire_by_step_id`` dict
    captures each leaf/transform's wire parameters so the async follow-up
    ``canonicalize_synced_parameters`` can fetch the search spec and decode
    them into typed ``ParamValue`` instances.
    """
    step_id = tree_node.step_id
    step = steps.get(str(step_id))
    if step is None:
        msg = (
            f"Step {step_id} not found in WDK steps dict "
            f"(available keys: {list(steps.keys())[:20]})"
        )
        raise DataParsingError(msg)

    search_name = step.search_name
    wire_parameters = step.search_config.parameters
    display_name = step.custom_name or step.display_name or None
    local_id = str(step_id)

    if tree_node.primary_input and tree_node.secondary_input:
        left = _build_node(tree_node.primary_input, steps, record_type, wire_by_step_id)
        right = _build_node(
            tree_node.secondary_input, steps, record_type, wire_by_step_id
        )
        raw_operator = _extract_operator(wire_parameters)
        if raw_operator is None:
            msg = (
                f"Combine step {step_id} has no boolean operator in "
                f"searchConfig.parameters (keys: {list(wire_parameters.keys())})"
            )
            raise DataParsingError(msg)
        expanded_strategy_id, expanded_name = _resolve_expanded_reference(
            step,
            right,
            steps,
        )
        return StrategyStepNode(
            search_name=search_name,
            operator=parse_op(raw_operator),
            primary_input=left,
            secondary_input=right,
            display_name=display_name,
            expanded_strategy_id=expanded_strategy_id,
            expanded_name=expanded_name,
            id=local_id,
        )
    wire_by_step_id[local_id] = dict(wire_parameters)
    if tree_node.primary_input:
        input_node = _build_node(
            tree_node.primary_input, steps, record_type, wire_by_step_id
        )
        return StrategyStepNode(
            search_name=search_name,
            primary_input=input_node,
            display_name=display_name,
            id=local_id,
        )
    return StrategyStepNode(
        search_name=search_name,
        display_name=display_name,
        id=local_id,
    )


def _extract_wdk_metadata(
    root: StrategyStepNode,
    wdk_steps: dict[str, WDKStep],
) -> tuple[dict[str, int], dict[str, int]]:
    """Extract step_counts and wdk_step_ids from plan tree matched against WDK steps."""
    step_counts: dict[str, int] = {}
    wdk_step_ids: dict[str, int] = {}
    for step in walk_step_tree(root):
        if not step.id.isdigit():
            continue
        wdk_id = int(step.id)
        wdk_step_ids[step.id] = wdk_id
        wdk_step = wdk_steps.get(str(wdk_id))
        if wdk_step is not None and wdk_step.estimated_size is not None:
            step_counts[step.id] = wdk_step.estimated_size
    return step_counts, wdk_step_ids


# -- Public API -----------------------------------------------------------------


def build_snapshot_from_wdk(
    wdk_strategy: WDKStrategyDetails,
) -> tuple[StrategyAst, dict[str, dict[str, str]]]:
    """Convert a typed WDK strategy into a StrategyAst plus a wire-params sidecar.

    Step counts and WDK step ID mappings are stored directly on the payload's
    ``step_counts`` and ``wdk_step_ids`` fields. Wire-form parameters for each
    leaf/transform step are returned separately so a follow-up async pass can
    fetch the matching WDK search spec and decode each value into a typed
    ``ParamValue``.
    """
    record_type = wdk_strategy.record_class_name or ""
    if not record_type.strip():
        msg = "WDK strategy is missing a valid 'recordClassName'"
        raise DataParsingError(msg)
    record_type = record_type.strip()

    wire_by_step_id: dict[str, dict[str, str]] = {}
    root = _build_node(
        wdk_strategy.step_tree,
        wdk_strategy.steps,
        record_type,
        wire_by_step_id,
    )

    step_counts, wdk_step_ids = _extract_wdk_metadata(root, wdk_strategy.steps)
    payload = StrategyAst(
        record_type=record_type,
        root=root,
        name=wdk_strategy.name or None,
        description=wdk_strategy.description or None,
        step_counts=step_counts or None,
        wdk_step_ids=wdk_step_ids or None,
    )
    return payload, wire_by_step_id


# -- Parameter normalization ----------------------------------------------------


async def _load_search_spec(
    api: StrategyAPI,
    record_type: str,
    search_name: str,
    context: dict[str, str],
) -> WDKSearch | None:
    """Load and unwrap search details for parameter normalization.

    Tries the context-aware endpoint first; falls back to the plain endpoint.
    Returns ``None`` when both fail.
    """
    try:
        response = await api.client.get_search_details_with_params(
            record_type,
            search_name,
            context=context,
            expand_params=True,
        )
    except AppError as exc:
        logger.warning(
            "Failed to load search details with params during WDK sync",
            record_type=record_type,
            search_name=search_name,
            error=str(exc),
        )
        try:
            response = await api.client.get_search_details(
                record_type, search_name, expand_params=True
            )
        except AppError as fallback_exc:
            logger.warning(
                "Failed to load search details during WDK sync",
                record_type=record_type,
                search_name=search_name,
                error=str(fallback_exc),
            )
            return None
    return response.search_data


async def canonicalize_synced_parameters(
    payload: StrategyAst,
    api: StrategyAPI,
    wire_by_step_id: dict[str, dict[str, str]],
) -> None:
    """Canonicalize parameters from WDK response using param specs.

    For each leaf/transform whose wire parameters were captured during
    ``build_snapshot_from_wdk``, fetch the WDK search spec, decode each
    wire value into a typed ``ParamValue`` via the spec's param kind,
    canonicalize (vocab match, leaf enforcement, range/scalar normalize),
    and write the result back onto ``step.parameters``.

    Mutates plan step nodes in place.
    """
    spec_cache: dict[tuple[str, str], WDKSearch | None] = {}

    for step in walk_step_tree(payload.root):
        if step.infer_kind() == "combine":
            continue
        search_name = step.search_name
        record_type = payload.record_type
        wire_params = wire_by_step_id.get(step.id)

        if not search_name or not record_type or not wire_params:
            continue

        cache_key = (record_type, search_name)
        if cache_key not in spec_cache:
            spec_cache[cache_key] = await _load_search_spec(
                api,
                record_type,
                search_name,
                wire_params,
            )

        cached_search = spec_cache.get(cache_key)
        specs = adapt_param_specs_from_search(cached_search) if cached_search else {}
        if not specs:
            continue
        kinds: dict[str, ParamKind] = {
            name: as_param_kind(spec.param_type) for name, spec in specs.items()
        }
        decoded = decode_params(wire_params, kinds)
        try:
            canonicalizer = ParameterCanonicalizer(specs)
            canonical = canonicalizer.canonicalize(decoded)
        except AppError as exc:
            logger.warning(
                "Failed to canonicalize synced parameters",
                record_type=record_type,
                search_name=search_name,
                step_id=step.id,
                error=str(exc),
            )
            continue

        step.parameters = canonical
