"""Full-flow integration tests: error handling and recovery.

Tests scenarios where the LLM provides invalid data and the system
returns actionable errors, allowing the model to self-correct.

All WDK calls are live.  Run with:

    pytest src/veupath_chatbot/tests/integration/test_full_flow_error_recovery.py -v -s

Skip with:

    pytest -m "not live_wdk"
"""

from __future__ import annotations

import json

import pytest

from veupath_chatbot.tests.fixtures.scripted_engine import (
    ScriptedToolCall,
    ScriptedTurn,
)
from veupath_chatbot.tests.fixtures.sse_collector import collect_chat_stream

pytestmark = pytest.mark.live_wdk


class TestInvalidParameterRecovery:
    """Model provides a non-existent organism name, gets a validation
    error, then corrects with a valid organism.

    This is extremely common in practice: LLMs frequently guess organism
    names slightly wrong (e.g., "P. falciparum" instead of
    "Plasmodium falciparum 3D7").
    """

    TURNS = [
        # First attempt: completely invalid organism name (not in WDK vocab)
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "create_step",
                    {
                        "search_name": "GenesWithEpitopes",
                        "record_type": "transcript",
                        "parameters": {
                            "organism": '["P. falciparum XYZ-nonexistent"]',
                            "epitope_confidence": '["High"]',
                        },
                    },
                )
            ]
        ),
        # Second attempt: correct organism
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "create_step",
                    {
                        "search_name": "GenesWithEpitopes",
                        "record_type": "transcript",
                        "parameters": {
                            "organism": '["Plasmodium falciparum 3D7"]',
                            "epitope_confidence": '["High"]',
                        },
                        "display_name": "Epitope genes (corrected)",
                    },
                )
            ]
        ),
        ScriptedTurn(
            content=(
                "I corrected the organism name and created the search "
                "with Plasmodium falciparum 3D7."
            )
        ),
    ]

    @pytest.mark.asyncio
    async def test_recovery(self, authed_client, scripted_engine_factory) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="Find epitope genes in P. falciparum",
                site_id="plasmodb",
                mode="execute",
                timeout=120.0,
            )

        assert result.http_status == 200
        types = result.event_types
        assert types[0] == "message_start"
        assert "message_end" in types

        # Should have two create_step calls
        create_step_pairs = [
            (s, e) for s, e in result.tool_calls if s.data.get("name") == "create_step"
        ]
        assert len(create_step_pairs) >= 2, (
            f"Expected 2 create_step calls (error + correction), "
            f"got {len(create_step_pairs)}"
        )

        # First call should contain an error in its result
        _, first_end = create_step_pairs[0]
        first_result_str = first_end.data.get("result", "{}")
        try:
            first_result = (
                json.loads(first_result_str)
                if isinstance(first_result_str, str)
                else first_result_str
            )
        except json.JSONDecodeError, TypeError:
            first_result = {}

        if isinstance(first_result, dict):
            # Should have error code or error message
            has_error = (
                first_result.get("errorCode") is not None
                or first_result.get("error") is not None
                or "error" in str(first_result).lower()
                or "validation" in str(first_result).lower()
            )
            assert has_error, (
                f"First create_step should return an error for invalid organism. "
                f"Got: {json.dumps(first_result, indent=2)[:500]}"
            )

        # Second call should succeed (has stepId)
        _, second_end = create_step_pairs[1]
        second_result_str = second_end.data.get("result", "{}")
        try:
            second_result = (
                json.loads(second_result_str)
                if isinstance(second_result_str, str)
                else second_result_str
            )
        except json.JSONDecodeError, TypeError:
            second_result = {}

        if isinstance(second_result, dict):
            assert second_result.get("stepId") or second_result.get("id"), (
                f"Second create_step should succeed. Got: {json.dumps(second_result, indent=2)[:500]}"
            )


class TestInvalidSearchNameRecovery:
    """Model tries a hallucinated search name, gets an error,
    searches the catalog to find the correct name, then succeeds.
    """

    TURNS = [
        # First attempt: hallucinated search name
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "create_step",
                    {
                        "search_name": "GenesByNonExistentSearch",
                        "record_type": "gene",
                        "parameters": {},
                    },
                )
            ]
        ),
        # Model searches catalog to find correct name
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "search_for_searches",
                    {"query": "epitope"},
                )
            ]
        ),
        # Second attempt with correct search name
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "create_step",
                    {
                        "search_name": "GenesWithEpitopes",
                        "record_type": "transcript",
                        "parameters": {
                            "organism": '["Plasmodium falciparum 3D7"]',
                            "epitope_confidence": '["High"]',
                        },
                    },
                )
            ]
        ),
        ScriptedTurn(content="Found the correct search name and created the step."),
    ]

    @pytest.mark.asyncio
    async def test_recovery(self, authed_client, scripted_engine_factory) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="Find epitope genes",
                site_id="plasmodb",
                mode="execute",
                timeout=120.0,
            )

        assert result.http_status == 200

        create_step_pairs = [
            (s, e) for s, e in result.tool_calls if s.data.get("name") == "create_step"
        ]
        assert len(create_step_pairs) >= 2

        # First should fail
        _, first_end = create_step_pairs[0]
        first_result_str = first_end.data.get("result", "{}")
        try:
            first_result = (
                json.loads(first_result_str)
                if isinstance(first_result_str, str)
                else first_result_str
            )
        except json.JSONDecodeError, TypeError:
            first_result = {}

        if isinstance(first_result, dict):
            has_error = (
                first_result.get("errorCode") is not None
                or "not_found" in str(first_result).lower()
                or "unknown" in str(first_result).lower()
                or "error" in str(first_result).lower()
            )
            assert has_error, f"Expected error for invalid search name: {first_result}"

        # search_for_searches should be called between the two create_steps
        tool_names = [s.data.get("name") for s, _ in result.tool_calls]
        first_create_idx = tool_names.index("create_step")
        search_idx = (
            tool_names.index("search_for_searches")
            if "search_for_searches" in tool_names
            else -1
        )
        assert search_idx > first_create_idx, (
            "search_for_searches should come after failed create_step"
        )

        # Second create_step should succeed
        _, second_end = create_step_pairs[1]
        second_result_str = second_end.data.get("result", "{}")
        try:
            second_result = (
                json.loads(second_result_str)
                if isinstance(second_result_str, str)
                else second_result_str
            )
        except json.JSONDecodeError, TypeError:
            second_result = {}

        if isinstance(second_result, dict):
            assert second_result.get("stepId") or second_result.get("id"), (
                f"Second create_step should succeed: {second_result}"
            )


class TestMissingRequiredParameters:
    """Model forgets required parameters.  The validation should return
    an error that lists the missing required params.
    """

    TURNS = [
        # Attempt with missing organism (required)
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "create_step",
                    {
                        "search_name": "GenesWithEpitopes",
                        "record_type": "transcript",
                        "parameters": {
                            "epitope_confidence": '["High"]',
                            # organism is missing
                        },
                    },
                )
            ]
        ),
        # Retry with all required params
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "create_step",
                    {
                        "search_name": "GenesWithEpitopes",
                        "record_type": "transcript",
                        "parameters": {
                            "organism": '["Plasmodium falciparum 3D7"]',
                            "epitope_confidence": '["High"]',
                        },
                    },
                )
            ]
        ),
        ScriptedTurn(
            content="Added the missing organism parameter and created the step."
        ),
    ]

    @pytest.mark.asyncio
    async def test_missing_params_error(
        self, authed_client, scripted_engine_factory
    ) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="Find epitope genes but I forgot to specify organism",
                site_id="plasmodb",
                mode="execute",
                timeout=120.0,
            )

        assert result.http_status == 200

        create_step_pairs = [
            (s, e) for s, e in result.tool_calls if s.data.get("name") == "create_step"
        ]
        assert len(create_step_pairs) >= 2

        # First should fail with validation error mentioning organism
        _, first_end = create_step_pairs[0]
        first_result_str = first_end.data.get("result", "")
        first_result_lower = str(first_result_str).lower()
        has_error = (
            "error" in first_result_lower
            or "validation" in first_result_lower
            or "required" in first_result_lower
            or "missing" in first_result_lower
        )
        result_preview = (
            str(first_result_str)[:500] if first_result_str is not None else ""
        )
        assert has_error, (
            f"Expected validation error for missing organism: {result_preview}"
        )

        # Second should succeed
        _, second_end = create_step_pairs[1]
        second_result_str = second_end.data.get("result", "{}")
        try:
            second_result = (
                json.loads(second_result_str)
                if isinstance(second_result_str, str)
                else second_result_str
            )
        except json.JSONDecodeError, TypeError:
            second_result = {}

        if isinstance(second_result, dict):
            assert second_result.get("stepId") or second_result.get("id")
