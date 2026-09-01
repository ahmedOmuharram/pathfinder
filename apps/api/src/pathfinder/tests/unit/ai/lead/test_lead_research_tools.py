"""The Lead carries the research tools itself, in every intent."""

from __future__ import annotations

from pydantic_ai import Tool

from pathfinder.ai.lead.intent_gate import BUILDING_TOOLS
from pathfinder.ai.lead.lead_agent import literature_search, web_search


def test_the_lead_has_both_research_tools() -> None:
    for tool in (web_search, literature_search):
        schema = Tool(tool).function_schema.json_schema
        assert "query" in schema["properties"]


def test_research_is_never_hidden_by_the_intent_gate() -> None:
    assert "web_search" not in BUILDING_TOOLS
    assert "literature_search" not in BUILDING_TOOLS
