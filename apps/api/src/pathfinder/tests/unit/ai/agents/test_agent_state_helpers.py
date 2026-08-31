"""Tests for the AgentToolState helpers that feed the dynamic toolset's
``Literal[...]`` enums. These are the ground-truth source for every
``parameter_id`` / ``search_name`` constraint that the model sees in
its tool schemas, so wrong values here would break the entire
hallucination-prevention story."""

from __future__ import annotations

from pathfinder.ai.agents.state import (
    AgentToolState,
    SearchOverview,
)
from pathfinder.domain.parameters.values import ParamValue, SinglePickValue


def _ov(
    name: str,
    *,
    parameter_names: list[str] | None = None,
) -> SearchOverview:
    return SearchOverview(
        search_name=name,
        display_name=name,
        record_type="transcript",
        description="",
        parameter_names=parameter_names or ["taxon"],
        required_params=["taxon"],
    )


def test_discovered_search_names_empty_initially() -> None:
    s = AgentToolState()
    assert s.discovered_search_names() == set()


def test_discovered_search_names_returns_all_inspected() -> None:
    s = AgentToolState()
    s.register_search("GenesByGoTerm", _ov("GenesByGoTerm"))
    s.register_search("GenesByText", _ov("GenesByText"))
    assert s.discovered_search_names() == {"GenesByGoTerm", "GenesByText"}


def test_a_search_overview_carries_no_selection_verdict() -> None:
    """No field records a verdict on a search: nothing writes one."""
    absent = {
        "selection_status",
        "rationale",
        "selection_reason",
        "confidence",
        "param_hints",
        "decided",
    }
    assert absent.isdisjoint(SearchOverview.model_fields)
    assert not hasattr(AgentToolState, "decided_search_names")
    assert not hasattr(AgentToolState, "selected_search_names")


def test_param_read_key_is_stable_and_context_sensitive() -> None:
    k1 = AgentToolState.param_read_key("S", "p")
    k2 = AgentToolState.param_read_key("S", "p")
    assert k1 == k2
    ctx_a: dict[str, ParamValue] = {"parent": SinglePickValue(value="a")}
    ctx_b: dict[str, ParamValue] = {"parent": SinglePickValue(value="b")}
    assert AgentToolState.param_read_key("S", "p", context_values=ctx_a) != k1
    assert AgentToolState.param_read_key(
        "S", "p", context_values=ctx_a
    ) != AgentToolState.param_read_key("S", "p", context_values=ctx_b)
    assert AgentToolState.param_read_key("S", "p", query="x") != k1


def test_mark_and_was_param_read() -> None:
    s = AgentToolState()
    key = AgentToolState.param_read_key("S", "p")
    assert s.was_param_read(key) is False
    s.mark_param_read(key)
    assert s.was_param_read(key) is True
