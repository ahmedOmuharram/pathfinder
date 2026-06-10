"""Tests for the AgentToolState helpers that feed the dynamic toolset's
``Literal[...]`` enums. These are the ground-truth source for every
``parameter_id`` / ``search_name`` constraint that the model sees in
its tool schemas, so wrong values here would break the entire
hallucination-prevention story."""

from __future__ import annotations

from pathfinder.ai.agents.state import AgentToolState, SearchOverview


def _ov(
    name: str,
    *,
    parameter_names: list[str] | None = None,
    selection_status: str = "candidate",
) -> SearchOverview:
    return SearchOverview(
        search_name=name,
        display_name=name,
        record_type="transcript",
        description="",
        parameter_names=parameter_names or ["taxon"],
        required_params=["taxon"],
        selection_status=selection_status,  # type: ignore[arg-type]
    )


def test_discovered_search_names_empty_initially() -> None:
    s = AgentToolState()
    assert s.discovered_search_names() == set()


def test_discovered_search_names_returns_all_inspected() -> None:
    s = AgentToolState()
    s.register_search("GenesByGoTerm", _ov("GenesByGoTerm"))
    s.register_search("GenesByText", _ov("GenesByText"))
    assert s.discovered_search_names() == {"GenesByGoTerm", "GenesByText"}


def test_selected_search_names_only_returns_selected_status() -> None:
    """``selected_search_names`` is the planner's universe — it must only
    include searches discovery committed to (not ``candidate`` /
    ``rejected``)."""
    s = AgentToolState()
    s.register_search(
        "GenesByGoTerm",
        _ov("GenesByGoTerm", selection_status="selected"),
    )
    s.register_search(
        "GenesByText",
        _ov("GenesByText", selection_status="candidate"),
    )
    s.register_search(
        "GenesByMicroarray",
        _ov("GenesByMicroarray", selection_status="rejected"),
    )
    assert s.selected_search_names() == {"GenesByGoTerm"}


def test_all_param_keys_unions_across_searches() -> None:
    """Flat union: when GenesByText has params {a,b} and GenesByGoTerm
    has {b,c}, the universe is {a,b,c}. Cross-search collisions (the
    shared `b`) are not resolved here — the tool body still verifies
    the param belongs to its specific search."""
    s = AgentToolState()
    s.register_search(
        "GenesByText",
        _ov("GenesByText", parameter_names=["query", "max_pvalue"]),
    )
    s.register_search(
        "GenesByGoTerm",
        _ov("GenesByGoTerm", parameter_names=["go_term", "max_pvalue"]),
    )
    assert s.all_param_keys() == {"query", "max_pvalue", "go_term"}


def test_param_keys_for_returns_only_that_search() -> None:
    """Per-search lookup is the precise variant — no cross-search
    leakage. Empty set for unknown searches (the dynamic toolset uses
    that signal to fall back to an unconstrained schema)."""
    s = AgentToolState()
    s.register_search(
        "GenesByText",
        _ov("GenesByText", parameter_names=["query", "max_pvalue"]),
    )
    s.register_search(
        "GenesByGoTerm",
        _ov("GenesByGoTerm", parameter_names=["go_term"]),
    )
    assert s.param_keys_for("GenesByText") == {"query", "max_pvalue"}
    assert s.param_keys_for("GenesByGoTerm") == {"go_term"}
    assert s.param_keys_for("NotInspected") == set()
