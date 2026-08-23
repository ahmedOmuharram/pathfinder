"""The site-help script's arcs, run through the real agent."""

from __future__ import annotations

from assistant_core.graph.runtime import AssistantDeps
from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest, ToolReturnPart

from pathfinder.assistants.site_help.agent import SiteSummary, build_site_help_agent
from pathfinder.assistants.site_help.mock import (
    CHECK_MARKER,
    CHECK_REPLY,
    LIST_SITES_TOOL,
    SITES_REPLY,
    build_site_help_mock,
)


def _deps() -> AssistantDeps:
    return AssistantDeps(site_id="plasmodb")


def _tool_returns(messages: list[object]) -> list[ToolReturnPart]:
    return [
        part
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]


async def test_the_marker_prompt_gets_the_fixed_reply() -> None:
    result = await build_site_help_agent().run(CHECK_MARKER, deps=_deps())

    assert result.output == CHECK_REPLY
    assert _tool_returns(list(result.all_messages())) == []


async def test_a_question_about_the_sites_calls_the_catalog_tool() -> None:
    result = await build_site_help_agent().run("which sites are there", deps=_deps())

    assert result.output == SITES_REPLY
    returns = _tool_returns(list(result.all_messages()))
    assert [part.tool_name for part in returns] == [LIST_SITES_TOOL]
    sites = returns[0].content
    assert isinstance(sites, list)
    ids = {site.site_id for site in sites if isinstance(site, SiteSummary)}
    assert {"plasmodb", "toxodb", "vectorbase"} <= ids


async def test_anything_else_falls_through_to_the_echo() -> None:
    result = await build_site_help_agent().run("tell me about kinases", deps=_deps())

    assert result.output == "[mock] tell me about kinases"
    assert _tool_returns(list(result.all_messages())) == []


async def test_an_agent_with_no_site_help_tool_gets_the_last_prompt_line() -> None:
    """The conversation-title agent offers no tools and must still get text."""
    titles: Agent[None, str] = Agent(
        build_site_help_mock(),
        output_type=str,
        instructions="Title it.",
        name="conversation-title",
    )

    result = await titles.run("User's first message:\nwhich sites are there")

    assert result.output == "which sites are there"
