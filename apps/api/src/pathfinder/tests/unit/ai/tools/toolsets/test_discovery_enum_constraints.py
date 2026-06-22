"""Tests for the discovery toolset's discovered-value constraints.

Discovery constrains ``search_name`` / ``parameter_id`` to the set the
agent has actually surfaced, killing the 404 hallucination-retry loop.
The constraint is enforced at CALL time by :class:`ValidatingEnumToolset`
(an invalid identifier raises ``ModelRetry`` naming the valid set), NOT
by injecting a per-request ``enum`` into the tool JSON schema. Keeping
the schema constant across the run is what lets the OpenAI/Anthropic
prompt-cache prefix stay warm — the old growing-enum rewrite busted the
cache every time a new search was discovered (≈440K input tokens for one
discovery dispatch in the captured turn).

These tests build a real ``RunContext`` (the shape pydantic-ai hands to
``get_tools`` / ``call_tool``), let the discovery toolset compute its
overrides, and assert on (a) the override sets, (b) the static schema,
and (c) the call-time ModelRetry guardrail.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
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
    hallucination loop) are rejected at call time."""
    state = AgentToolState()
    state.record_catalog_searches(["GenesByGoTerm", "GenesByText"])
    overrides = _discovery_enum_overrides(_ctx(state))
    assert overrides[("get_search_overview", "search_name")] == [
        "GenesByGoTerm",
        "GenesByText",
    ]


def test_get_search_overview_candidates_include_already_inspected() -> None:
    """An inspected search stays inspectable even if it isn't in the latest
    catalog listing (re-inspection must not be blocked)."""
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


# ---- Schema stays STATIC (prompt-cache prefix stability) ----


@pytest.mark.asyncio
async def test_schema_carries_no_enum_even_after_inspection() -> None:
    """The cache-stability invariant: no matter how many searches/params
    have been discovered, the tool JSON schema must NOT gain an injected
    ``enum``. A constant schema keeps the OpenAI/Anthropic prompt-cache
    prefix warm across the whole discovery loop."""
    state = AgentToolState()
    state.register_search(
        "GenesByGoTerm",
        _ov("GenesByGoTerm", ["go_term", "taxon"]),
    )
    state.register_search("GenesByText", _ov("GenesByText", ["query"]))
    toolset = build_toolset()
    tools = await toolset.get_tools(_ctx(state))
    props = tools["get_parameter_options"].tool_def.parameters_json_schema["properties"]  # type: ignore[index]
    assert "enum" not in props["parameter_id"]
    assert "enum" not in props["search_name"]


@pytest.mark.asyncio
async def test_cold_start_schema_has_no_enum() -> None:
    """Before any inspection the schema also carries no enum — same
    static shape, so the prefix is identical from the first request."""
    toolset = build_toolset()
    tools = await toolset.get_tools(_ctx(AgentToolState()))
    props = tools["get_parameter_options"].tool_def.parameters_json_schema["properties"]  # type: ignore[index]
    assert "enum" not in props["parameter_id"]
    assert "enum" not in props["search_name"]


# ---- Call-time validation guardrail (the moved constraint) ----


@pytest.mark.asyncio
async def test_invalid_search_name_raises_model_retry() -> None:
    """An inspect call on a name the agent never surfaced is rejected
    with ModelRetry naming the valid candidates — no WDK round-trip."""
    state = AgentToolState()
    state.record_catalog_searches(["GenesByGoTerm", "GenesByText"])
    toolset = build_toolset()
    ctx = _ctx(state)
    tool = (await toolset.get_tools(ctx))["get_search_overview"]
    with pytest.raises(ModelRetry) as exc:
        await toolset.call_tool(
            "get_search_overview", {"search_name": "GenesByImaginary"}, ctx, tool
        )
    msg = str(exc.value)
    assert "GenesByImaginary" in msg
    assert "GenesByGoTerm" in msg
    assert "GenesByText" in msg


@pytest.mark.asyncio
async def test_cold_start_inspect_is_not_blocked() -> None:
    """With no catalog listing yet, get_search_overview has no override,
    so any name passes validation (it then hits the real tool body)."""
    state = AgentToolState()
    toolset = build_toolset()
    ctx = _ctx(state)
    tool = (await toolset.get_tools(ctx))["get_search_overview"]
    overrides = _discovery_enum_overrides(ctx)
    assert ("get_search_overview", "search_name") not in overrides
    del tool  # cold-start validation is a no-op; body execution needs WDK I/O
