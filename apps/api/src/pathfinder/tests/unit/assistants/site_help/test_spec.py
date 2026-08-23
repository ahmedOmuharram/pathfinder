"""Site help declares a whole assistant, and declares nothing PathFinder owns."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from assistant_core.graph.runtime import TurnContext
from assistant_core.graph.turn_state import TurnState
from assistant_core.spec import TurnContextRequest, TurnStart
from langgraph.checkpoint.memory import InMemorySaver
from pydantic_ai.models.function import FunctionModel

from pathfinder.assistants.registry import get_assistant_registry
from pathfinder.assistants.site_help.spec import (
    SITE_HELP_ASSISTANT_ID,
    build_site_help_spec,
)


def test_the_registry_serves_it_alongside_pathfinder() -> None:
    registry = get_assistant_registry()

    assert set(registry.ids()) == {"pathfinder", SITE_HELP_ASSISTANT_ID}
    assert registry.default_id == "pathfinder"
    assert registry.resolve(SITE_HELP_ASSISTANT_ID).assistant_id == "site_help"


def test_its_graph_is_one_agent_and_the_runtime_s_finalize() -> None:
    compiled = build_site_help_spec().build_graph(InMemorySaver())

    assert set(compiled.get_graph().nodes) >= {"agent", "finalize_turn"}
    assert "lead" not in compiled.get_graph().nodes


def test_its_state_is_the_bare_turn_state() -> None:
    start = TurnStart(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        turn_message_id=uuid4(),
        turn_start_event_id=0,
        user_prompt="which sites are there",
    )

    state = build_site_help_spec().build_initial_state(start)

    assert type(state) is TurnState
    assert state.user_prompt == "which sites are there"


async def test_its_turn_context_carries_no_domain_session() -> None:
    request = TurnContextRequest(
        conversation=None,
        site_id="plasmodb",
        user_id=uuid4(),
        memory_store=None,
        cancel_event=asyncio.Event(),
        phase_models={},
        phase_reasoning={},
    )

    context = await build_site_help_spec().build_turn_context(request)

    assert type(context) is TurnContext
    assert context.site_id == "plasmodb"


def test_it_declares_no_identity_requirement_and_no_extras() -> None:
    spec = build_site_help_spec()

    assert spec.identity_gate is None
    assert spec.register_stream_parts is None
    assert spec.turn_epilogue is None
    assert spec.memory_kinds == frozenset()
    assert spec.checkpoint_types == ()


def test_its_mock_factory_returns_its_own_script() -> None:
    model = build_site_help_spec().build_mock_model()

    assert isinstance(model, FunctionModel)
