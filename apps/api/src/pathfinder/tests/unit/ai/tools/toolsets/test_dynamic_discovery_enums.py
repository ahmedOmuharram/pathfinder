"""End-to-end tests for the discovery toolset's per-step enum injection.

These tests build a real ``RunContext`` (the same shape pydantic-ai
hands to ``get_tools``), let the discovery toolset's ``DynamicEnumToolset``
wrapper compute its overrides, and assert on the JSON schema the model
will actually receive. The schema is what OpenAI's strict mode and
Anthropic's constrained generation read to mask non-enum tokens at
sampling time — so if the enum doesn't land here, the whole
hallucination-prevention story is broken.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from pydantic_ai import RunContext
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pydantic_ai.usage import RunUsage

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.toolsets.discovery import (
    _discovery_enum_overrides,
    build_toolset,
)
from pathfinder.domain.strategy.session import StrategySession


def _stub_model() -> FunctionModel:
    """Real pydantic-ai Model — needed because FunctionToolset.get_tools
    calls dataclasses.replace(run_context, ...) and that requires a
    real RunContext (which in turn requires a real Model)."""

    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart(content="ok")])

    async def _stream(
        messages: list[ModelMessage],
        info: AgentInfo,
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del messages, info
        yield "ok"

    return FunctionModel(_fn, stream_function=_stream, model_name="test")


def _ov(name: str, parameter_names: list[str]) -> SearchOverview:
    return SearchOverview(
        search_name=name,
        display_name=name,
        record_type="transcript",
        description="",
        parameter_names=parameter_names,
        required_params=parameter_names[:1],
    )


def _ctx(state: AgentToolState) -> RunContext[AgentDeps]:
    """Real RunContext — the toolset's wrapped FunctionToolset calls
    dataclasses.replace on it internally so a MagicMock won't do."""
    deps = AgentDeps(
        site_id="plasmodb",
        strategy_session=StrategySession(site_id="plasmodb"),
        agent_state=state,
    )
    return RunContext(deps=deps, model=_stub_model(), usage=RunUsage())


# ---- Override builder shape ----


def test_overrides_empty_on_cold_start() -> None:
    """Cold start: no inspections, no overrides. The model must be free
    to browse / search / list with unconstrained args."""
    assert _discovery_enum_overrides(_ctx(AgentToolState())) == {}


def test_overrides_constrain_search_name_after_first_inspection() -> None:
    """Once ANY search is inspected, the search_name arg of the three
    inspection-dependent tools is locked to the inspected set."""
    state = AgentToolState()
    state.register_search(
        "GenesByGoTerm",
        _ov("GenesByGoTerm", ["go_term", "taxon"]),
    )
    overrides = _discovery_enum_overrides(_ctx(state))
    assert overrides[("update_search_decision", "search_name")] == [
        "GenesByGoTerm",
    ]
    assert overrides[("get_parameter_options", "search_name")] == [
        "GenesByGoTerm",
    ]
    assert overrides[("get_parameter_dependencies", "search_name")] == [
        "GenesByGoTerm",
    ]


def test_get_search_overview_unconstrained_on_cold_start() -> None:
    """Before any catalog listing, the model must be free to inspect any
    search name returned by search_for_searches it hasn't recorded yet."""
    overrides = _discovery_enum_overrides(_ctx(AgentToolState()))
    assert ("get_search_overview", "search_name") not in overrides


def test_get_search_overview_constrained_to_catalog_candidates() -> None:
    """Once search_for_searches / list_searches have returned names, the
    model may only inspect one of THOSE names — invented names (the 404
    hallucination loop) are masked at sampling time."""
    state = AgentToolState()
    state.record_catalog_searches(["GenesByGoTerm", "GenesByText"])
    overrides = _discovery_enum_overrides(_ctx(state))
    assert overrides[("get_search_overview", "search_name")] == [
        "GenesByGoTerm",
        "GenesByText",
    ]


def test_get_search_overview_candidates_include_already_inspected() -> None:
    """An inspected search stays inspectable even if it isn't in the latest
    catalog listing (re-inspection must not be masked)."""
    state = AgentToolState()
    state.record_catalog_searches(["GenesByText"])
    state.register_search("GenesByGoTerm", _ov("GenesByGoTerm", ["go_term"]))
    overrides = _discovery_enum_overrides(_ctx(state))
    assert overrides[("get_search_overview", "search_name")] == [
        "GenesByGoTerm",
        "GenesByText",
    ]


def test_overrides_constrain_parameter_id_after_inspection() -> None:
    """parameter_id constrains to the flat union of params across all
    inspected searches (the body still verifies per-search membership)."""
    state = AgentToolState()
    state.register_search(
        "GenesByGoTerm",
        _ov("GenesByGoTerm", ["go_term", "taxon"]),
    )
    state.register_search(
        "GenesByText",
        _ov("GenesByText", ["query", "max_pvalue"]),
    )
    overrides = _discovery_enum_overrides(_ctx(state))
    assert overrides[("get_parameter_options", "parameter_id")] == [
        "go_term",
        "max_pvalue",
        "query",
        "taxon",
    ]


# ---- Tool schema actually carries the enum ----


@pytest.mark.asyncio
async def test_get_parameter_options_schema_carries_enum() -> None:
    """The whole point: when the agent calls ``toolset.get_tools(ctx)``,
    the JSON schema for ``parameter_id`` MUST include an ``enum`` keyed
    on the discovered params. OpenAI strict / Anthropic constrained
    generation reads this enum and refuses to emit any other value."""
    state = AgentToolState()
    state.register_search(
        "GenesByGoTerm",
        _ov("GenesByGoTerm", ["go_term", "taxon"]),
    )
    state.register_search(
        "GenesByText",
        _ov("GenesByText", ["query"]),
    )
    toolset = build_toolset()
    tools = await toolset.get_tools(_ctx(state))
    tool = tools["get_parameter_options"]
    schema = tool.tool_def.parameters_json_schema
    properties = schema["properties"]  # type: ignore[index]
    assert properties["parameter_id"]["enum"] == [
        "go_term",
        "query",
        "taxon",
    ]
    # search_name is also constrained to the inspected set.
    assert properties["search_name"]["enum"] == [
        "GenesByGoTerm",
        "GenesByText",
    ]


@pytest.mark.asyncio
async def test_unrelated_tools_unchanged() -> None:
    """Override only applies to the tools we listed in the override
    builder. Tools like ``think`` or ``get_record_types`` must keep
    their original schemas."""
    state = AgentToolState()
    state.register_search(
        "GenesByGoTerm",
        _ov("GenesByGoTerm", ["go_term"]),
    )
    toolset = build_toolset()
    tools = await toolset.get_tools(_ctx(state))
    think_tool = tools["think"]
    schema = think_tool.tool_def.parameters_json_schema
    properties = schema["properties"]  # type: ignore[index]
    # The think tool's "thought" arg should remain a plain string with
    # no enum injected — our override targets are surgical.
    for prop in properties.values():
        assert "enum" not in prop, f"unrelated tool got an enum override: {prop!r}"


@pytest.mark.asyncio
async def test_cold_start_schema_has_no_enum() -> None:
    """Before any search is inspected, parameter_id must NOT have an
    enum (else the model could not call get_parameter_options at all
    on a freshly-discovered search before we've inspected it)."""
    toolset = build_toolset()
    tools = await toolset.get_tools(_ctx(AgentToolState()))
    schema = tools["get_parameter_options"].tool_def.parameters_json_schema
    properties = schema["properties"]  # type: ignore[index]
    assert "enum" not in properties["parameter_id"]
    assert "enum" not in properties["search_name"]


@pytest.mark.asyncio
async def test_base_toolset_definition_not_mutated() -> None:
    """Subtle but critical: the wrapper must NOT mutate the wrapped
    toolset's cached parameters_json_schema. If it did, every later
    request would inherit stale enums and the model would see
    ever-growing constraint sets that don't match current state."""
    state_a = AgentToolState()
    state_a.register_search("A", _ov("A", ["alpha"]))
    state_b = AgentToolState()
    state_b.register_search("B", _ov("B", ["beta"]))

    toolset = build_toolset()

    tools_a = await toolset.get_tools(_ctx(state_a))
    enum_a = tools_a["get_parameter_options"].tool_def.parameters_json_schema[
        "properties"
    ]["parameter_id"]["enum"]
    assert enum_a == ["alpha"]

    tools_b = await toolset.get_tools(_ctx(state_b))
    enum_b = tools_b["get_parameter_options"].tool_def.parameters_json_schema[
        "properties"
    ]["parameter_id"]["enum"]
    assert enum_b == ["beta"]
    # And the first request's schema is still {alpha} — not contaminated
    # with {beta} from the later request.
    enum_a_after = tools_a["get_parameter_options"].tool_def.parameters_json_schema[
        "properties"
    ]["parameter_id"]["enum"]
    assert enum_a_after == ["alpha"]
