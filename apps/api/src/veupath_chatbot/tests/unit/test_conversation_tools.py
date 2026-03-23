"""Tests for ai.tools.conversation_tools -- save/rename/clear/summarize logic."""

from uuid import uuid4

from veupath_chatbot.ai.tools.conversation_tools import ConversationTools
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.session import StrategyGraph, StrategySession


def _make_session_with_graph(
    *, with_strategy: bool = True, strategy_name: str = "Test Strategy"
) -> tuple[StrategySession, StrategyGraph]:
    session = StrategySession("plasmodb")
    graph = session.create_graph(strategy_name, graph_id="g1")
    if with_strategy:
        step = PlanStepNode(search_name="GenesByText", parameters={"text": "kinase"})
        graph.add_step(step)
        graph.record_type = "gene"
        graph.description = "A test strategy"
    return session, graph


# -- save_strategy --


async def test_save_strategy_success():
    session, graph = _make_session_with_graph()
    tools = ConversationTools(session)

    result = await tools.save_strategy(name="My saved strategy", graph_id=graph.id)

    assert result["ok"] is True
    assert result["name"] == "My saved strategy"
    assert result["graphId"] == graph.id
    assert result["recordType"] == "gene"
    assert "plan" in result


async def test_save_strategy_updates_graph_name():
    session, graph = _make_session_with_graph()
    tools = ConversationTools(session)

    await tools.save_strategy(name="New Name", graph_id=graph.id)

    assert graph.name == "New Name"


async def test_save_strategy_updates_description():
    session, graph = _make_session_with_graph()
    tools = ConversationTools(session)

    result = await tools.save_strategy(
        name="S", description="Updated description", graph_id=graph.id
    )

    assert result["description"] == "Updated description"


async def test_save_strategy_graph_not_found():
    session = StrategySession("plasmodb")
    tools = ConversationTools(session)

    result = await tools.save_strategy(name="X", graph_id="nonexistent")

    assert result["ok"] is False
    assert result["code"] == "NOT_FOUND"


async def test_save_strategy_no_strategy():
    session, graph = _make_session_with_graph(with_strategy=False)
    tools = ConversationTools(session)

    result = await tools.save_strategy(name="X", graph_id=graph.id)

    assert result["ok"] is False
    assert result["code"] == "INVALID_STRATEGY"


# -- rename_strategy --


async def test_rename_strategy_success():
    session, graph = _make_session_with_graph(strategy_name="Old Name")
    tools = ConversationTools(session)

    result = await tools.rename_strategy(
        new_name="New Name", description="New desc", graph_id=graph.id
    )

    assert result["ok"] is True
    assert result["oldName"] == "Old Name"
    assert result["newName"] == "New Name"
    assert result["name"] == "New Name"
    assert graph.name == "New Name"


async def test_rename_strategy_no_strategy():
    session, graph = _make_session_with_graph(with_strategy=False)
    tools = ConversationTools(session)

    result = await tools.rename_strategy(
        new_name="X", description="Y", graph_id=graph.id
    )

    assert result["ok"] is False
    assert result["code"] == "INVALID_STRATEGY"


async def test_rename_strategy_saves_history():
    session, graph = _make_session_with_graph(strategy_name="Original")
    tools = ConversationTools(session)

    await tools.rename_strategy(new_name="Renamed", description="D", graph_id=graph.id)

    assert len(graph.history) > 0
    last = graph.history[-1]
    assert "Renamed" in str(last.get("description", ""))


# -- clear_strategy --


async def test_clear_strategy_requires_confirmation():
    session, graph = _make_session_with_graph()
    tools = ConversationTools(session)

    result = await tools.clear_strategy(graph_id=graph.id, confirm=False)

    assert result["ok"] is False
    assert result["code"] == "VALIDATION_ERROR"
    assert "confirmation" in str(result["message"]).lower()


async def test_clear_strategy_with_confirmation():
    session, graph = _make_session_with_graph()
    tools = ConversationTools(session)

    result = await tools.clear_strategy(graph_id=graph.id, confirm=True)

    assert result["ok"] is True
    assert result["cleared"] is True
    assert len(graph.steps) == 0
    assert len(graph.roots) == 0
    assert graph.last_step_id is None


# -- get_strategy_summary --


async def test_get_strategy_summary_with_strategy():
    session, graph = _make_session_with_graph(strategy_name="My Strategy")
    tools = ConversationTools(session)

    result = await tools.get_strategy_summary(graph_id=graph.id)

    assert result["hasStrategy"] is True
    assert result["name"] == "My Strategy"
    assert result["recordType"] == "gene"
    assert result["stepCount"] == 1


async def test_get_strategy_summary_without_strategy():
    session, graph = _make_session_with_graph(with_strategy=False)
    # Add a loose step without a strategy
    step = PlanStepNode(search_name="GenesByText", parameters={})
    graph.add_step(step)
    tools = ConversationTools(session)

    result = await tools.get_strategy_summary(graph_id=graph.id)

    # Now the graph has steps, so it has a strategy
    assert result["hasStrategy"] is True


async def test_get_strategy_summary_empty_graph():
    session, graph = _make_session_with_graph(with_strategy=False)
    tools = ConversationTools(session)

    result = await tools.get_strategy_summary(graph_id=graph.id)

    assert result["hasStrategy"] is False
    assert result["stepCount"] == 0
    assert "No complete strategy" in str(result["message"])


async def test_get_strategy_summary_graph_not_found():
    session = StrategySession("plasmodb")
    tools = ConversationTools(session)

    result = await tools.get_strategy_summary(graph_id="missing")

    assert result["ok"] is False
    assert result["code"] == "NOT_FOUND"


# -- edge case: user_id --


async def test_save_strategy_with_user_id():
    session, graph = _make_session_with_graph()
    uid = uuid4()
    tools = ConversationTools(session, user_id=uid)

    result = await tools.save_strategy(name="S", graph_id=graph.id)

    assert result["ok"] is True
