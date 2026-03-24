"""Test that ToolCallStartEventData accepts parsed arguments from kani.

Kani's FunctionCall.kwargs returns a parsed dict from the JSON arguments string.
The call site in streaming.py passes kwargs (always a dict), never the raw string.
"""

from veupath_chatbot.platform.event_schemas import ToolCallStartEventData


class TestToolCallStartArguments:
    def test_dict_arguments_accepted(self) -> None:
        event = ToolCallStartEventData(
            id="tc_1",
            name="search",
            arguments={"query": "P. falciparum orthologs", "limit": 3},
        )
        assert event.arguments == {"query": "P. falciparum orthologs", "limit": 3}

    def test_empty_dict_default(self) -> None:
        event = ToolCallStartEventData(id="tc_1", name="list_steps")
        assert event.arguments == {}

    def test_nested_arguments(self) -> None:
        event = ToolCallStartEventData(
            id="tc_1",
            name="search",
            arguments={"filters": {"organism": ["P. falciparum"]}, "limit": 5},
        )
        assert event.arguments["filters"] == {"organism": ["P. falciparum"]}
