"""Tests for push-immediately behaviour in edit_ops (PUT search-config on update)."""

from unittest.mock import AsyncMock, patch

from veupath_chatbot.ai.tools.strategy_tools.edit_ops import StrategyEditOps
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.session import StrategyGraph, StrategySession
from veupath_chatbot.platform.errors import AppError, ErrorCode

_VALIDATE_PARAMS = (
    "veupath_chatbot.ai.tools.strategy_tools.edit_ops.validate_parameters"
)
_GET_STRATEGY_API = "veupath_chatbot.ai.tools.strategy_tools.edit_ops.get_strategy_api"


def _make_edit_ops(
    *, graph_id: str = "g1", wdk_step_id: int | None = None
) -> tuple[StrategyEditOps, StrategyGraph, PlanStepNode]:
    """Create a StrategyEditOps with a single step, optionally pre-mapped to a WDK ID."""
    session = StrategySession("plasmodb")
    graph = session.create_graph("test", graph_id=graph_id)
    graph.record_type = "gene"

    step = PlanStepNode(
        search_name="GenesByTaxon", parameters={"organism": "Plasmodium falciparum"}
    )
    graph.add_step(step)

    if wdk_step_id is not None:
        graph.wdk_step_ids[step.id] = wdk_step_id

    ops = StrategyEditOps.__new__(StrategyEditOps)
    ops.session = session
    return ops, graph, step


# -- _apply_step_updates pushes search-config --


async def test_apply_step_updates_puts_search_config_when_wdk_id_present():
    """When a step has a WDK ID, updating parameters should PUT search-config."""
    ops, graph, step = _make_edit_ops(wdk_step_id=42)

    mock_api = AsyncMock()
    with (
        patch(_VALIDATE_PARAMS, new_callable=AsyncMock),
        patch(_GET_STRATEGY_API, return_value=mock_api),
    ):
        error = await ops._apply_step_updates(
            graph,
            step,
            search_name=None,
            parameters={"organism": "Toxoplasma gondii"},
            operator=None,
            display_name=None,
        )

    assert error is None


async def test_apply_step_updates_skips_push_when_no_wdk_id():
    """When a step has no WDK ID, no PUT should be attempted."""
    ops, graph, step = _make_edit_ops(wdk_step_id=None)

    mock_api = AsyncMock()
    with (
        patch(_VALIDATE_PARAMS, new_callable=AsyncMock),
        patch(_GET_STRATEGY_API, return_value=mock_api),
    ):
        error = await ops._apply_step_updates(
            graph,
            step,
            search_name=None,
            parameters={"organism": "Toxoplasma gondii"},
            operator=None,
            display_name=None,
        )

    assert error is None


async def test_apply_step_updates_skips_push_when_only_search_name_changes():
    """When parameters is None (only search_name changed), no PUT should fire."""
    ops, graph, step = _make_edit_ops(wdk_step_id=42)

    mock_api = AsyncMock()
    with patch(_GET_STRATEGY_API, return_value=mock_api):
        error = await ops._apply_step_updates(
            graph,
            step,
            search_name="NewSearchName",
            parameters=None,
            operator=None,
            display_name=None,
        )

    assert error is None


async def test_apply_step_updates_logs_warning_on_app_error():
    """If the PUT fails with AppError, it should log a warning and NOT raise."""
    ops, graph, step = _make_edit_ops(wdk_step_id=42)

    mock_api = AsyncMock()
    mock_api.update_step_search_config.side_effect = AppError(
        ErrorCode.WDK_ERROR, "WDK is down"
    )

    with (
        patch(_VALIDATE_PARAMS, new_callable=AsyncMock),
        patch(_GET_STRATEGY_API, return_value=mock_api),
    ):
        error = await ops._apply_step_updates(
            graph,
            step,
            search_name=None,
            parameters={"organism": "Toxoplasma gondii"},
            operator=None,
            display_name=None,
        )

    # Should not raise — error is swallowed with a warning
    assert error is None


async def test_apply_step_updates_logs_warning_on_os_error():
    """If the PUT fails with OSError, it should log a warning and NOT raise."""
    ops, graph, step = _make_edit_ops(wdk_step_id=42)

    mock_api = AsyncMock()
    mock_api.update_step_search_config.side_effect = OSError("Connection refused")

    with (
        patch(_VALIDATE_PARAMS, new_callable=AsyncMock),
        patch(_GET_STRATEGY_API, return_value=mock_api),
    ):
        error = await ops._apply_step_updates(
            graph,
            step,
            search_name=None,
            parameters={"organism": "Toxoplasma gondii"},
            operator=None,
            display_name=None,
        )

    assert error is None


async def test_apply_step_updates_converts_param_values_to_strings():
    """Parameter values must be stringified for WDKSearchConfig."""
    ops, graph, step = _make_edit_ops(wdk_step_id=42)

    mock_api = AsyncMock()
    with (
        patch(_VALIDATE_PARAMS, new_callable=AsyncMock),
        patch(_GET_STRATEGY_API, return_value=mock_api),
    ):
        error = await ops._apply_step_updates(
            graph,
            step,
            search_name=None,
            parameters={"threshold": 42, "flag": True},
            operator=None,
            display_name=None,
        )

    assert error is None


async def test_apply_step_updates_excludes_none_param_values():
    """None values in parameters should be excluded from the WDKSearchConfig."""
    ops, graph, step = _make_edit_ops(wdk_step_id=42)

    mock_api = AsyncMock()
    with (
        patch(_VALIDATE_PARAMS, new_callable=AsyncMock),
        patch(_GET_STRATEGY_API, return_value=mock_api),
    ):
        error = await ops._apply_step_updates(
            graph,
            step,
            search_name=None,
            parameters={"organism": "Plasmodium", "optional_field": None},
            operator=None,
            display_name=None,
        )

    assert error is None


async def test_apply_step_updates_no_substantive_change_skips_push():
    """When only display_name changes (no substantive change), no push should happen."""
    ops, graph, step = _make_edit_ops(wdk_step_id=42)

    mock_api = AsyncMock()
    with patch(_GET_STRATEGY_API, return_value=mock_api):
        error = await ops._apply_step_updates(
            graph,
            step,
            search_name=None,
            parameters=None,
            operator=None,
            display_name="Pretty Name",
        )

    assert error is None
    assert step.display_name == "Pretty Name"


# -- delete_step no longer calls invalidate_build --


async def test_delete_step_does_not_crash_without_invalidate_build():
    """delete_step should work without invalidate_build (removed in Task 2)."""
    ops, graph, step = _make_edit_ops(wdk_step_id=100)
    # Add a second step so deletion doesn't remove all steps
    step_b = PlanStepNode(search_name="SearchB", parameters={"y": "2"})
    graph.add_step(step_b)

    result = await ops.delete_step(step_id=step.id, graph_id="g1")

    assert step.id not in graph.steps
    assert step_b.id in graph.steps
    assert step.id in result.get("deleted", [])
